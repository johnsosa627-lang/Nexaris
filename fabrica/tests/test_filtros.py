import math

import numpy as np
import pandas as pd
import pytest

from fabrica import filtros as F
from fabrica.generador import Evaluador
from fabrica.motor import Costos
from tests.conftest import serie_mercado


def ops(retornos):
    n = len(retornos)
    return pd.DataFrame({"retorno": retornos, "precio_entrada": [100.0] * n, "precio_salida": [101.0] * n,
                         "apalancamiento": [0.5] * n})


def test_montecarlo():
    rng = np.random.default_rng(0)
    buena = F.montecarlo(ops([0.01, -0.005] * 200), 0.05, 500, 10, 2, rng)
    assert buena["pct_ganadoras"] == 100 and buena["drawdown_p95_pct"] < 15
    mala = F.montecarlo(ops([0.005, -0.006] * 200), 0.05, 500, 10, 2, rng)
    assert mala["pct_ganadoras"] < 5
    # duplicar comisiones resta 0,5 * 0,05% * (100+101)/100 en cada operación
    sin_extra = F.montecarlo(ops([0.001] * 10), 0.05, 1, 0, 1, rng)
    con_extra = F.montecarlo(ops([0.001] * 10), 0.05, 1, 0, 2, rng)
    esperado = (1 + 0.001 - 0.5 * 0.0005 * 2.01) ** 10 - 1
    assert con_extra["retorno_mediana_pct"] == pytest.approx(esperado * 100)
    assert sin_extra["retorno_mediana_pct"] == pytest.approx((1.001 ** 10 - 1) * 100)


def test_deflated_sharpe():
    # sin ensayos múltiples equivale al Probabilistic Sharpe Ratio
    psr = F.deflated_sharpe(0.1, 400, 0, 3, 1, 0)
    assert psr == pytest.approx(F.NORMAL.cdf(0.1 * math.sqrt(399) / math.sqrt(1 + 0.5 * 0.01)))
    # cuantas más estrategias probadas, más exigente
    pocas = F.deflated_sharpe(0.15, 400, 0, 3, 10, 1 / 400)
    muchas = F.deflated_sharpe(0.15, 400, 0, 3, 10000, 1 / 400)
    assert pocas > muchas
    assert F.deflated_sharpe(0.4, 400, 0, 3, 5000, 1 / 400) > 0.99
    assert F.deflated_sharpe(0.0, 400, 0, 3, 5000, 1 / 400) < 0.01


def test_precios_al_azar_conserva_forma_y_rompe_orden():
    v = serie_mercado(3000, 1, 0.2)
    fund = np.arange(3000) * 1e-6
    azar, fund_azar = F.precios_al_azar(v, np.random.default_rng(0), fund)
    r_orig = np.sort(np.diff(np.log(v["close"].to_numpy())))
    r_azar = np.sort(np.diff(np.log(azar["close"].to_numpy())))
    np.testing.assert_allclose(r_orig, r_azar, atol=1e-12)
    assert (azar["high"] >= azar[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (azar["low"] <= azar[["open", "close"]].min(axis=1) + 1e-9).all()
    assert (azar["ts"] == v["ts"]).all() and sorted(fund_azar) == sorted(fund)
    # la autocorrelación (la "tendencia" escondida) desaparece
    def autocorr(df):
        r = np.diff(np.log(df["close"].to_numpy()))
        return np.corrcoef(r[:-1], r[1:])[0, 1]
    assert autocorr(v) > 0.15 and abs(autocorr(azar)) < 0.05


def _combo(v, otros=(), vecinos=(), suerte=0.0):
    ev = Evaluador(v, None, Costos())
    return F.Combo("X", "1h", ev, int(len(v) * 0.7), lambda: list(otros), lambda: list(vecinos),
                   lambda: {"fitness_max": suerte}, 100, 1 / 500)


CFG = {"min_operaciones": 50, "min_profit_factor": 1.3, "min_ret_dd": 3, "max_drawdown_pct": 20,
       "min_estabilidad": 0.8, "min_pct_anios_positivos": 50, "oos_min_profit_factor": 1.1, "wf_ventanas": 4,
       "wf_variantes": 3, "wf_min_pct_ventanas_positivas": 60, "wf_min_profit_factor": 1.1,
       "montecarlo_simulaciones": 200, "montecarlo_confianza_pct": 95, "montecarlo_saltear_pct": 10,
       "montecarlo_multiplicador_comision": 2, "robustez_variantes": 6, "robustez_min_pct_rentables": 80,
       "robustez_min_ret_dd_relativo": 0.5, "otras_monedas_min_pct": 50, "temporalidad_vecina_min": 1,
       "retraso_min_profit_factor": 1.1, "antisuerte_margen": 1.2, "dsr_min": 0.95}

TENDENCIA = {"lado": "ambos", "reglas": [{"tipo": "ruptura_donchian", "n": 20}],
             "salidas": {"stop_tipo": "atr", "stop": 2.0, "tp_tipo": "ninguno", "tp": 0.0, "trailing": 3.0, "max_velas": 0}}


def _candidata(ev_is, est):
    from fabrica.generador import fitness
    m = ev_is.correr(est).metricas
    return {"estrategia": est, "metricas": m, "fitness": fitness(m, est, 35)}


def test_estrategia_con_ventaja_real_pasa_todo():
    v = serie_mercado(16000, 11, 0.25)
    otros = [(f"M{i}", Evaluador(serie_mercado(8000, 20 + i, 0.25), None, Costos())) for i in range(3)]
    vecino = [("4h", Evaluador(serie_mercado(4000, 30, 0.25), None, Costos()))]
    combo = _combo(v, otros, vecino, suerte=1.0)
    cand = _candidata(Evaluador(v.iloc[:11200], None, Costos()), TENDENCIA)
    pasos = F.aplicar_filtros(cand, combo, CFG, np.random.default_rng(0))
    assert [p[0] for p in pasos] == [f[0] for f in F.FILTROS]
    assert all(ok for _, ok, _ in pasos), pasos
    assert cand["montecarlo"]["pct_ganadoras"] >= 95 and cand["antisuerte"]["dsr"] >= 0.95


def test_se_corta_en_el_primer_filtro_que_falla():
    v = serie_mercado(8000, 12, 0.0)  # azar puro
    combo = _combo(v)
    cand = _candidata(Evaluador(v.iloc[:5600], None, Costos()), TENDENCIA)
    pasos = F.aplicar_filtros(cand, combo, CFG, np.random.default_rng(0))
    assert not pasos[-1][1] and all(ok for _, ok, _ in pasos[:-1])


def test_filtros_individuales():
    v = serie_mercado(8000, 11, 0.2)
    rng = np.random.default_rng(1)
    cand = _candidata(Evaluador(v.iloc[:5600], None, Costos()), TENDENCIA)
    combo = _combo(v)
    assert F.f1_metricas(cand, combo, CFG, rng)[0]
    # sin otras monedas no se puede verificar => no pasa (prudencia)
    assert not F.f5_otros_mercados(cand, combo, CFG, rng)[0]
    # si la suerte da casi lo mismo, no pasa el anti-suerte
    assert not F.f7_antisuerte(cand, _combo(v, suerte=cand["fitness"]), CFG, rng)[0]
    # exigir demasiado en Monte Carlo
    assert not F.f3_montecarlo(cand, combo, {**CFG, "montecarlo_confianza_pct": 100.1}, rng)[0]
