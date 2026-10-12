import numpy as np
import pandas as pd
import pytest

from tests.conftest import velas, velas_aleatorias
from fabrica.motor import Costos, Salidas, _nucleo, backtest

SIN_COSTOS = Costos(0, 0, False, 0)
PCT = Salidas("pct", 2, "pct", 4)


def senal(n, en):
    a = np.zeros(n, dtype=bool)
    for i in en:
        a[i] = True
    return a


def correr(filas, largo=(), corto=(), salidas=PCT, costos=SIN_COSTOS, **kw):
    v = velas(filas)
    n = len(v)
    return backtest(v, senal(n, largo), senal(n, corto), salidas, costos, **kw)


BASE = [(100, 100.5, 99.5, 100)] * 2


def test_long_take_profit_sin_costos():
    r = correr(BASE + [(101, 105, 100.5, 104), (104, 104, 103, 103.5)], largo=[0])
    op = r.operaciones.iloc[0]
    assert op["lado"] == "LONG" and op["motivo"] == "take-profit"
    assert op["precio_entrada"] == 100 and op["precio_salida"] == pytest.approx(104)
    # riesgo 1%: stop a 2% => posición de 0,5x el capital; +4% de precio => +2% del capital = 2R
    assert op["retorno"] == pytest.approx(0.02) and op["r"] == pytest.approx(2)
    assert op["entrada_ts"] == r.operaciones["entrada_ts"].iloc[0]
    assert len(r.operaciones) == 1


def test_entrada_es_en_la_apertura_siguiente():
    r = correr([(100, 101, 99, 100), (107, 108, 106, 107)] + [(107, 107.5, 106.5, 107)] * 2, largo=[0])
    assert r.operaciones.iloc[0]["precio_entrada"] == 107


def test_comisiones_y_slippage():
    c = Costos(0.05, 0.02, False, 0.03)
    r = correr(BASE + [(101, 105, 100.5, 104)], largo=[0], costos=c)
    op = r.operaciones.iloc[0]
    pe = 100 * 1.0002
    tp = pe * 1.04
    ps = tp * (1 - 0.0002)
    pnl = (ps - pe) - 0.0005 * (pe + ps)
    assert op["precio_entrada"] == pytest.approx(pe)
    assert op["precio_salida"] == pytest.approx(ps)
    assert op["retorno"] == pytest.approx(0.5 * pnl / pe)
    assert op["retorno"] < 0.02


def test_stop_loss_y_hueco():
    r = correr(BASE + [(99, 99.5, 97, 97.5)], largo=[0])
    op = r.operaciones.iloc[0]
    assert op["motivo"] == "stop-loss" and op["precio_salida"] == pytest.approx(98)
    assert op["retorno"] == pytest.approx(-0.01) and op["r"] == pytest.approx(-1)
    r = correr(BASE + [(95, 96, 94, 95.5)], largo=[0])  # abre por debajo del stop
    assert r.operaciones.iloc[0]["precio_salida"] == 95
    assert r.operaciones.iloc[0]["r"] == pytest.approx(-2.5)


def test_slippage_extra_en_stops():
    c = Costos(0, 0, False, 0.03)
    op = correr(BASE + [(99, 99.5, 97, 97.5)], largo=[0], costos=c).operaciones.iloc[0]
    assert op["precio_salida"] == pytest.approx(98 * (1 - 0.0003))
    op = correr(BASE + [(101, 105, 100.5, 104)], largo=[0], costos=c).operaciones.iloc[0]
    assert op["precio_salida"] == pytest.approx(104)  # el take-profit (orden límite) no lleva el extra
    op = correr(BASE + [(95, 96, 94, 95.5)], largo=[0], costos=c).operaciones.iloc[0]
    assert op["precio_salida"] == 95  # hueco: ya se llena al precio real de apertura


def test_stop_y_tp_en_la_misma_vela_cuenta_como_stop():
    r = correr(BASE + [(100, 105, 97, 104)], largo=[0])
    assert r.operaciones.iloc[0]["motivo"] == "stop-loss"


def test_short():
    r = correr(BASE + [(99, 99.5, 95, 96)], corto=[0])
    op = r.operaciones.iloc[0]
    assert op["lado"] == "SHORT" and op["motivo"] == "take-profit"
    assert op["precio_salida"] == pytest.approx(96) and op["retorno"] == pytest.approx(0.02)
    r = correr(BASE + [(101, 102.5, 100.5, 102)], corto=[0])
    assert r.operaciones.iloc[0]["motivo"] == "stop-loss" and r.operaciones.iloc[0]["r"] == pytest.approx(-1)


def test_funding_long_paga_y_short_cobra():
    filas = BASE + [(101, 101.5, 100.5, 101), (101, 101.5, 100.5, 101)]
    fund = np.array([0, 0, 0.001, 0])
    largo = correr(filas, largo=[0], funding=fund, costos=Costos(0, 0, True, 0))
    corto = correr(filas, corto=[0], funding=fund, costos=Costos(0, 0, True, 0))
    sin = correr(filas, largo=[0], funding=fund, costos=Costos(0, 0, False, 0))
    pago = 0.001 * 101
    assert largo.operaciones.iloc[0]["funding_por_unidad"] == pytest.approx(pago)
    assert largo.operaciones.iloc[0]["retorno"] == pytest.approx(sin.operaciones.iloc[0]["retorno"] - 0.5 * pago / 100)
    assert corto.operaciones.iloc[0]["funding_por_unidad"] == pytest.approx(-pago)


def test_salida_por_tiempo_y_por_senal():
    filas = BASE + [(100, 101, 99.5, 100.5), (100.5, 101, 100, 100.8), (100.8, 101, 100, 100.2)]
    r = correr(filas, largo=[0], salidas=Salidas("pct", 2, "pct", 4, max_velas=2))
    op = r.operaciones.iloc[0]
    assert op["motivo"] == "tiempo" and op["precio_salida"] == pytest.approx(100.5) and op["velas"] == 2
    v = velas(filas)
    r = backtest(v, senal(5, [0]), senal(5, []), PCT, SIN_COSTOS, sal_long=senal(5, [2]))
    op = r.operaciones.iloc[0]
    assert op["motivo"] == "señal de salida" and op["precio_salida"] == pytest.approx(100.5)  # apertura de la vela 3


def test_stop_movil():
    filas = BASE + [(100, 103, 99.5, 102.5), (102.5, 102.6, 100.5, 101)]
    r = correr(filas, largo=[0], salidas=Salidas("pct", 2, "ninguno", 0, trailing=2))
    op = r.operaciones.iloc[0]
    assert op["motivo"] == "stop móvil" and op["precio_salida"] == pytest.approx(101)


def test_retraso_de_una_vela():
    filas = [(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (102, 102.5, 101.5, 102), (102, 102.5, 101.5, 102)]
    r = correr(filas, largo=[0], retraso=1)
    assert r.operaciones.iloc[0]["precio_entrada"] == 102


def test_tope_de_apalancamiento():
    r = correr([(100, 100.05, 99.95, 100)] * 2 + [(100, 100.4, 99.95, 100.3)], largo=[0], salidas=Salidas("pct", 0.1, "pct", 0.3),
               apalancamiento_max=3)
    op = r.operaciones.iloc[0]
    assert op["apalancamiento"] == 3  # 1% / 0,1% = 10x, recortado a 3x
    assert op["retorno"] == pytest.approx(3 * 0.003)


def test_stop_obligatorio():
    for s in (Salidas("pct", 0), Salidas("ninguno", 2), Salidas("pct", -1)):
        with pytest.raises(ValueError):
            correr(BASE * 2, largo=[0], salidas=s)


def test_una_sola_posicion_a_la_vez():
    filas = [(100, 100.5, 99.5, 100)] * 10
    r = correr(filas, largo=[0, 1, 2, 3], salidas=Salidas("pct", 2, "pct", 4))
    assert len(r.operaciones) == 1 and r.operaciones.iloc[0]["motivo"] == "fin de datos"


def _senales_aleatorias(n, semilla):
    rng = np.random.default_rng(semilla)
    return rng.random(n) < 0.03, rng.random(n) < 0.03, rng.random(n) < 0.02, rng.random(n) < 0.02


def test_no_mira_el_futuro():
    v = velas_aleatorias(1500, semilla=4)
    l, c, sl, sc = _senales_aleatorias(1500, 1)
    s = Salidas("atr", 1.5, "atr", 3, trailing=2, max_velas=40)
    completo = backtest(v, l, c, s, Costos(), sal_long=sl, sal_short=sc).operaciones
    corte = 900
    alterado = v.copy()
    rng = np.random.default_rng(9)
    alterado.loc[corte:, ["open", "high", "low", "close"]] *= rng.uniform(0.5, 1.5, (1500 - corte, 1))
    alterado["high"] = alterado[["open", "high", "low", "close"]].max(axis=1)
    alterado["low"] = alterado[["open", "high", "low", "close"]].min(axis=1)
    parcial = backtest(alterado, l, c, s, Costos(), sal_long=sl, sal_short=sc).operaciones
    ts_corte = v["ts"].iloc[corte]
    a = completo[completo["salida_ts"] < ts_corte].reset_index(drop=True)
    b = parcial[parcial["salida_ts"] < ts_corte].reset_index(drop=True)
    assert len(a) > 10
    pd.testing.assert_frame_equal(a, b)


def test_numba_y_python_dan_lo_mismo():
    if not hasattr(_nucleo, "py_func"):
        pytest.skip("numba no instalado")
    v = velas_aleatorias(3000, semilla=7)
    l, c, sl, sc = _senales_aleatorias(3000, 2)
    from fabrica.indicadores import atr
    a = atr(v["high"], v["low"], v["close"]).to_numpy()
    fund = np.where(np.arange(3000) % 8 == 0, 0.0001, 0.0)
    args = (v["open"].to_numpy(), v["high"].to_numpy(), v["low"].to_numpy(), v["close"].to_numpy(), a,
            l, c, sl, sc, fund, 1, 1.5, 0, 3.0, 2.0, 30, 0.0005, 0.0002, 0, 0.01, 3.0, 0.0003)
    for x, y in zip(_nucleo(*args), _nucleo.py_func(*args)):
        np.testing.assert_allclose(x, y)


def test_velocidad_razonable():
    import time
    v = velas_aleatorias(140_000, semilla=1, vol=0.003)  # ~4 años de velas de 15m
    l, c, _, _ = _senales_aleatorias(140_000, 3)
    backtest(v.iloc[:500], l[:500], c[:500], PCT)  # compila
    t = time.time()
    r = backtest(v, l, c, Salidas("atr", 2, "atr", 4, trailing=3), Costos())
    assert r.metricas["operaciones"] > 100
    assert time.time() - t < 5
