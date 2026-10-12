import json

import numpy as np
import pytest

from fabrica import estrategia as E
from tests.conftest import velas_aleatorias


def test_aleatorias_validas_y_json():
    rng = np.random.default_rng(0)
    ctx = E.Contexto(velas_aleatorias(800))
    for _ in range(300):
        e = E.estrategia_aleatoria(rng)
        assert e["reglas"][0]["tipo"] in E.DISPARADORES
        assert all(c["tipo"] in E.FILTROS for c in e["reglas"][1:]) and len(e["reglas"]) <= 3
        assert len({c["tipo"] for c in e["reglas"]}) == len(e["reglas"])
        assert e["salidas"]["stop"] > 0
        assert json.loads(json.dumps(e)) == e
        assert E.identificador(e) == E.identificador(json.loads(json.dumps(e)))
        largo, corto = E.senales(ctx, e)
        assert largo.dtype == bool and len(largo) == 800
        if e["lado"] == "long":
            assert not corto.any()
        if e["lado"] == "short":
            assert not largo.any()
        assert "Stop-loss" in E.describir(e)


def test_regla_espejo_exacta():
    """Las señales de venta sobre un precio son las de compra sobre el precio dado vuelta."""
    v = velas_aleatorias(1500, semilla=2)
    espejo = v.copy()
    espejo["open"], espejo["close"] = -v["open"], -v["close"]
    espejo["high"], espejo["low"] = -v["low"], -v["high"]
    ctx, ctx_e = E.Contexto(v), E.Contexto(espejo)
    rng = np.random.default_rng(3)
    probadas = 0
    for _ in range(200):
        e = E.estrategia_aleatoria(rng)
        e["lado"] = "ambos"
        largo, corto = E.senales(ctx, e)
        largo_e, corto_e = E.senales(ctx_e, e)
        assert (corto == largo_e).mean() > 0.999 and (largo == corto_e).mean() > 0.999
        probadas += corto.any()
    assert probadas > 100


def test_condiciones_a_mano():
    import pandas as pd
    from tests.conftest import velas
    filas = [(10, 10, 10, 10)] * 30 + [(10, 13, 10, 12)] + [(12, 12.5, 11.5, 12)] * 3
    ctx = E.Contexto(velas(filas))
    cruce = E.condicion(ctx, {"tipo": "cruce_precio_media", "media": "sma", "n": 20}, 1)
    assert cruce[30] and cruce.sum() == 1
    ruptura = E.condicion(ctx, {"tipo": "ruptura_donchian", "n": 10}, 1)
    assert ruptura[30] and not ruptura[31]
    tendencia = E.condicion(ctx, {"tipo": "tendencia", "media": "sma", "n": 20}, 1)
    assert tendencia[30:].all() and not tendencia[:30].any()
    assert not E.condicion(ctx, {"tipo": "tendencia", "media": "sma", "n": 20}, -1)[30:].any()


def test_mutar_cruzar_perturbar_siguen_validas():
    rng = np.random.default_rng(1)
    ctx = E.Contexto(velas_aleatorias(500))
    for _ in range(300):
        a, b = E.estrategia_aleatoria(rng), E.estrategia_aleatoria(rng)
        for hija in (E.mutar(rng, a), E.cruzar(rng, a, b), E.perturbar(rng, a, 2)):
            assert hija["reglas"][0]["tipo"] in E.DISPARADORES and len(hija["reglas"]) <= 3
            for c in hija["reglas"]:
                if c["tipo"] == "cruce_medias":
                    assert c["rapida"] < c["lenta"]
            E.senales(ctx, hija)
        assert a == json.loads(json.dumps(a))  # las operaciones no modifican a los padres


def test_perturbar_mueve_poco():
    rng = np.random.default_rng(4)
    e = {"lado": "ambos", "reglas": [{"tipo": "cruce_medias", "media": "ema", "rapida": 20, "lenta": 50}],
         "salidas": {"stop_tipo": "atr", "stop": 2.0, "tp_tipo": "atr", "tp": 4.0, "trailing": 0.0, "max_velas": 0}}
    for _ in range(50):
        p = E.perturbar(rng, e, 1)
        r = p["reglas"][0]
        assert r["rapida"] in (13, 20, 21) and r["lenta"] in (34, 50, 55)
        assert p["salidas"]["stop"] in (1.5, 2.0, 2.5) and p["salidas"]["tp"] in (3.0, 4.0, 5.0)
        assert p != e  # siempre cambia algo


def test_perturbar_siempre_cambia_algo():
    rng = np.random.default_rng(8)
    for _ in range(500):
        e = E.estrategia_aleatoria(rng)
        assert E.perturbar(rng, e, 1) != e


def test_describir():
    e = {"lado": "long", "reglas": [{"tipo": "ruptura_donchian", "n": 20}, {"tipo": "volumen_filtro", "mult": 1.5}],
         "salidas": {"stop_tipo": "pct", "stop": 2.0, "tp_tipo": "pct", "tp": 4.0, "trailing": 0.0, "max_velas": 48}}
    t = E.describir(e)
    assert "Solo compra" in t and "máximo de las últimas 20 velas" in t and "1.5 veces" in t
    assert "2.0%" in t and "48 velas" in t and "ATR" not in t
