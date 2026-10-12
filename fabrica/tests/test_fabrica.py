import copy
import random

import numpy as np
import pandas as pd
import pytest

from fabrica import ciclo as C
from fabrica import datos as D
from fabrica import estrategia as E
from fabrica import liga as L
from fabrica import metricas as M
from fabrica import robustez as R
from fabrica.config import cargar
from fabrica.generador import cruzar, evolucionar, mutar
from fabrica.indicadores import Cache
from fabrica.motor import correr


@pytest.fixture(autouse=True)
def data_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "EXAMINADOS", tmp_path / "examinados.json")
    monkeypatch.setattr(C, "CONTADOR", tmp_path / "contador.json")
    monkeypatch.setattr(C, "DATA_DIR", tmp_path)
    monkeypatch.setattr(L, "ARCHIVO", tmp_path / "liga.json")


@pytest.fixture
def cfg():
    c = cargar()
    c["generador"].update(poblacion=20, generaciones=2, semilla=1)
    c["filtros"].update(anti_suerte_rondas=1, montecarlo_simulaciones=100, perturbacion_variantes=4)
    return c


def test_indicadores_no_miran_el_futuro():
    df = D.sintetico(3000, 2)
    full = Cache(df)
    corto = Cache(df.iloc[:2000])
    r = random.Random(0)
    for _ in range(30):
        e = E.al_azar(r)
        a = E.senal(e, full)[:2000]
        b = E.senal(e, corto)
        assert (a[200:] == b[200:]).all(), E.explicar(e)


def test_stop_gana_en_empate_y_costos_se_descuentan():
    n = 60
    df = pd.DataFrame({"ts": np.arange(n) * 3_600_000, "open": 100.0, "high": 101.0, "low": 99.0,
                       "close": 100.0, "volume": 1.0})
    df.loc[40, ["high", "low"]] = [130.0, 70.0]  # toca stop y take-profit en la misma vela
    e = {"lado": "long", "condiciones": [{"tipo": "volumen", "n": 10, "x": 0.0}], "sl_atr": 3.0, "tp_atr": 3.0,
         "max_barras": 100, "atr_n": 14}
    res = correr(e, Cache(df), 35, n, costo_rt=0.0, funding_8h=0)
    assert res.r[0] == pytest.approx(-1.0)
    res2 = correr(e, Cache(df), 35, n, costo_rt=0.01, funding_8h=0)
    assert res2.r[0] < -1.0 and res2.costo_r[0] > 0


def test_entrada_en_la_vela_siguiente():
    df = D.sintetico(500, 3)
    e = {"lado": "long", "condiciones": [{"tipo": "rsi", "n": 14, "op": ">", "x": 50}], "sl_atr": 2,
         "tp_atr": 2, "max_barras": 10, "atr_n": 14}
    c = Cache(df)
    res = correr(e, c, 0, None)
    s = E.senal(e, c)
    for ent in res.entradas:
        assert s[ent - 1]


def test_metricas_basicas():
    r = np.array([1, -1, 2, -1, 1, 1, -1, 2] * 10, dtype=float)
    m = M.calcular(r)
    assert m["operaciones"] == 80
    assert m["profit_factor"] == pytest.approx(7 / 3, rel=1e-3)
    assert m["win_rate"] == pytest.approx(5 / 8)
    assert 0 < m["max_dd"] < 0.05
    assert m["racha_perdidas"] == 1


def test_deflated_sharpe_baja_con_mas_pruebas():
    a = M.deflated_sharpe(0.15, 300, 10)
    b = M.deflated_sharpe(0.15, 300, 100000)
    assert a > b


def test_mutar_y_cruzar_dan_estrategias_validas():
    r = random.Random(5)
    c = Cache(D.sintetico(800, 5))
    for _ in range(50):
        a, b = E.al_azar(r), E.al_azar(r)
        for h in (mutar(a, r, 3), cruzar(a, b, r, 3)):
            assert 1 <= len(h["condiciones"]) <= 3
            correr(h, c, 0, None)
            E.explicar(h)


def test_montecarlo_y_variantes():
    r = np.random.default_rng(0).normal(0.2, 1, 300)
    mc = R.montecarlo(r, np.full(300, 0.05), {"montecarlo_simulaciones": 200, "montecarlo_saltear": 0.1,
                                               "montecarlo_costo_extra": 1.0}, 0.01)
    assert mc["dd_p99"] >= mc["dd_p95"] > 0
    e = E.al_azar(random.Random(1))
    assert len(R.variantes(e, 5)) == 5


def test_barajar_mantiene_volatilidad():
    df = D.sintetico(3000, 7)
    f = D.barajar(df, 1)
    a = np.std(np.diff(np.log(df["close"])))
    b = np.std(np.diff(np.log(f["close"])))
    assert a == pytest.approx(b, rel=1e-6)
    assert (f["high"] >= f[["open", "close"]].max(axis=1) - 1e-9).all()


def test_ciclo_completo_en_datos_al_azar_no_aprueba_nada(cfg):
    """En precios 100 % al azar no hay nada real que encontrar: los filtros deben rechazar todo."""
    conj = {("AAA/USDT:USDT", "1h"): D.sintetico(9000, 11), ("BBB/USDT:USDT", "1h"): D.sintetico(9000, 12)}
    inf = C.correr_ciclo(cfg, conj)
    assert inf["embudo"]["inventadas"] > 0
    assert inf["ganadoras"] == []
    assert "Inventadas" in C.texto_embudo(inf)


def test_liga_asciende_y_jubila(cfg):
    df = D.sintetico(4000, 21)
    c = {("AAA/USDT:USDT", "1h"): Cache(df)}
    e = {"lado": "long", "condiciones": [{"tipo": "rsi", "n": 14, "op": ">", "x": 50}], "sl_atr": 2,
         "tp_atr": 2, "max_barras": 20, "atr_n": 14, "simbolo": "AAA/USDT:USDT", "tf": "1h"}
    g = {"id": "x1", "estrategia": e, "explicacion": E.explicar(e), "puntaje": 70,
         "metricas_datos_nuevos": {"expectancy_r": 0.1}, "montecarlo": {"dd_p95": 0.99}}
    liga = L.leer()
    assert L.agregar_candidatos(liga, [g], cfg) == ["x1"]
    liga["suplentes"][0]["alta"] = int(df["ts"].iloc[1000])
    avisos = L.revisar(liga, c, cfg)
    assert liga["titulares"] and "titular" in avisos[0]
    liga["titulares"][0]["titular_desde"] = int(df["ts"].iloc[1000])
    cu = L.cuenta_papel(liga, c, cfg)
    assert cu["operaciones"] > 0 and cu["capital"] > 0
    # si cae más de lo previsto por Monte Carlo, se jubila
    liga["titulares"][0]["montecarlo"]["dd_p95"] = 0.0001
    avisos = L.revisar(liga, c, cfg)
    assert not liga["titulares"] and liga["jubilados"]
    L.guardar(liga)
    assert L.leer()["jubilados"][0]["id"] == "x1"


def test_pausa_excluye_operaciones(cfg):
    df = D.sintetico(4000, 22)
    c = {("AAA/USDT:USDT", "1h"): Cache(df)}
    e = {"lado": "long", "condiciones": [{"tipo": "rsi", "n": 14, "op": ">", "x": 50}], "sl_atr": 2,
         "tp_atr": 2, "max_barras": 20, "atr_n": 14, "simbolo": "AAA/USDT:USDT", "tf": "1h"}
    b = {"id": "y", "estrategia": e, "alta": int(df["ts"].iloc[500]), "titular_desde": int(df["ts"].iloc[500])}
    liga = {"titulares": [b], "suplentes": [], "jubilados": []}
    sin = L.cuenta_papel(liga, c, cfg)["operaciones"]
    liga["pausas"] = [[int(df["ts"].iloc[500]), None]]
    assert L.cuenta_papel(liga, c, cfg)["operaciones"] == 0 < sin
