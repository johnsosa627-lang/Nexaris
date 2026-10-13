"""Datos de afuera del gráfico: funding, Bitcoin como líder y Miedo y Codicia."""
import numpy as np
import pandas as pd
import pytest

from fabrica import datos
from fabrica.estrategia import Contexto, condicion, estrategia_aleatoria, EXTERNOS
from fabrica.generador import Evaluador, evolucionar
from fabrica.motor import Costos
from tests.conftest import H, T0, serie_mercado

DIA = 86_400_000


def test_alinear_sin_mirar_el_futuro():
    ts = T0 + np.arange(30, dtype="int64") * H
    funding = pd.DataFrame({"ts": [T0 + 8 * H, T0 + 16 * H], "tasa": [0.0001, -0.0002]})
    f = datos.alinear_ultimo(ts, funding, "tasa", "1h")
    assert np.isnan(f[:7]).all()          # todavía no se conocía ningún funding
    assert f[7] == 0.0001                 # la vela de las 7h cierra a las 8h: ya se conoce
    assert f[15] == -0.0002 and f[29] == -0.0002
    fng = pd.DataFrame({"ts": [T0, T0 + DIA], "valor": [20.0, 80.0]})
    ts_d = T0 + np.arange(72, dtype="int64") * H
    v = datos.alinear_ultimo(ts_d, fng, "valor", "1h", demora_ms=DIA)
    assert np.isnan(v[:23]).all()         # el índice de un día recién se usa al día siguiente
    assert v[23] == 20 and v[47] == 80


def test_externos_para_alinea_bitcoin_por_fecha():
    v = serie_mercado(100, 1)
    btc = serie_mercado(100, 2)
    btc = btc.iloc[5:].reset_index(drop=True)  # le faltan las primeras 5 velas
    ext = datos.externos_para(v["ts"].to_numpy(), "1h", pd.DataFrame(columns=["ts", "tasa"]), btc,
                              pd.DataFrame(columns=["ts", "valor"]))
    assert np.isnan(ext["btc"][:5]).all() and ext["btc"][5] == btc["close"].iloc[0]
    assert np.isnan(ext["funding"]).all() and np.isnan(ext["fng"]).all()


def test_condiciones_externas_y_espejo():
    v = serie_mercado(60, 1)
    ext = {"funding": np.linspace(-0.05, 0.05, 60), "fng": np.linspace(0, 100, 60),
           "btc": np.concatenate([np.linspace(100, 50, 30), np.linspace(50, 120, 30)])}
    ctx = Contexto(v, ext)
    f = condicion(ctx, {"tipo": "funding_filtro", "nivel": 0.0}, 1)
    assert f[:29].all() and not f[31:].any()
    assert condicion(ctx, {"tipo": "funding_filtro", "nivel": 0.0}, -1)[31:].all()
    m = condicion(ctx, {"tipo": "miedo_codicia", "op": "<", "nivel": 30}, 1)
    assert m[:17].all() and not m[18:].any()
    assert condicion(ctx, {"tipo": "miedo_codicia", "op": "<", "nivel": 30}, -1)[43:].all()  # espejo: codicia > 70
    b = condicion(ctx, {"tipo": "btc_tendencia", "n": 20}, 1)
    assert not b[20:30].any() and b[-1]
    sin = Contexto(v)  # sin datos externos: nunca se cumple (no opera a ciegas)
    for c in ({"tipo": "funding_filtro", "nivel": 0.03}, {"tipo": "btc_tendencia", "n": 20},
              {"tipo": "miedo_codicia", "op": ">", "nivel": 20}):
        assert not condicion(sin, c, 1).any() and not condicion(sin, c, -1).any()


def _mercado_con_animo(n=8000, semilla=3):
    """El precio rebota cuando hay miedo (índice < 30) y cae cuando hay codicia (> 70): un patrón real."""
    rng = np.random.default_rng(semilla)
    dias = n // 24 + 2
    fng_dia = np.repeat(rng.choice([15.0, 50.0, 85.0], dias // 8 + 1), 8)[:dias]  # rachas de 8 días
    ts = T0 + np.arange(n, dtype="int64") * H
    fng = pd.DataFrame({"ts": T0 + np.arange(dias, dtype="int64") * DIA, "valor": fng_dia})
    animo = datos.alinear_ultimo(ts, fng, "valor", "1h", demora_ms=DIA)
    deriva = np.where(animo < 30, 0.0015, np.where(animo > 70, -0.0015, 0.0))
    r = rng.normal(0, 0.006, n) + np.nan_to_num(deriva)
    c = 100 * np.exp(np.cumsum(r))
    o = np.concatenate([[100.0], c[:-1]])
    v = pd.DataFrame({"ts": ts, "open": o, "high": np.maximum(o, c) * 1.002, "low": np.minimum(o, c) * 0.998,
                      "close": c, "volume": 1000.0})
    return v, {"fng": animo, "funding": np.zeros(n), "btc": c}


def test_un_dato_externo_que_anticipa_el_precio_mejora_la_estrategia():
    v, ext = _mercado_con_animo()
    ev = Evaluador(v, None, Costos(), externos=ext)
    base = {"lado": "long", "reglas": [{"tipo": "cruce_precio_media", "media": "ema", "n": 20}],
            "salidas": {"stop_tipo": "atr", "stop": 2.0, "tp_tipo": "atr", "tp": 3.0, "trailing": 0.0, "max_velas": 48}}
    con_miedo = {**base, "reglas": base["reglas"] + [{"tipo": "miedo_codicia", "op": "<", "nivel": 30}]}
    sin = ev.correr(base).metricas
    con = ev.correr(con_miedo).metricas
    assert con["operaciones"] > 20
    assert con["profit_factor"] > sin["profit_factor"] and con["profit_factor"] > 1.2


def test_la_fabrica_prueba_las_piezas_externas():
    v, ext = _mercado_con_animo(4000)
    ev = Evaluador(v, None, Costos(), externos=ext)
    archivo = evolucionar(ev, np.random.default_rng(1), poblacion=40, generaciones=3, min_operaciones=60)
    usadas = [a for a in archivo.values() if any(c["tipo"] in EXTERNOS for c in a["estrategia"]["reglas"])]
    assert usadas and any(a["metricas"]["operaciones"] > 0 for a in usadas)
