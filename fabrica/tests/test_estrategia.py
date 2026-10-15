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


def test_piezas_nuevas_a_mano():
    v = velas_aleatorias(600, semilla=5)
    ctx = E.Contexto(v)
    # horario: 0-8 UTC = Asia; las velas son de 1 hora desde las 00:00
    asia = E.condicion(ctx, {"tipo": "horario", "tramo": "asia"}, 1)
    assert asia[:8].all() and not asia[8:24].any()
    assert (asia == E.condicion(ctx, {"tipo": "horario", "tramo": "asia"}, -1)).all()
    # volatilidad: > y < son complementarios donde hay datos
    mas = E.condicion(ctx, {"tipo": "volatilidad", "op": ">", "nivel": 1.0}, 1)
    menos = E.condicion(ctx, {"tipo": "volatilidad", "op": "<", "nivel": 1.0}, 1)
    assert not (mas & menos).any() and mas[200:].any() and menos[200:].any()
    # retroceso_rsi y ruptura_compresion dan alguna señal y nunca en las primeras velas (sin datos)
    for c in ({"tipo": "retroceso_rsi", "n": 2, "nivel": 10}, {"tipo": "ruptura_compresion", "n": 20, "m": 50}):
        s = E.condicion(ctx, c, 1)
        assert s.any() and not s[:3].any()
        assert "UTC" in E.describir_condicion({"tipo": "horario", "tramo": "europa"})


def test_famosas_validas_y_en_la_poblacion():
    from fabrica.famosas import famosas
    from fabrica.generador import Evaluador, evolucionar
    from fabrica.motor import Costos
    v = velas_aleatorias(1500, semilla=7)
    ctx = E.Contexto(v)
    lista = famosas()
    assert len({E.identificador(e) for e in lista}) == len(lista)
    for e in lista:
        assert e["reglas"][0]["tipo"] in E.DISPARADORES and all(c["tipo"] in E.FILTROS for c in e["reglas"][1:])
        E.senales(ctx, e)
        assert E.describir(e).startswith("[Basada en una estrategia conocida")
        assert "famosa" not in E.mutar(np.random.default_rng(0), e) and "famosa" not in E.perturbar(np.random.default_rng(0), e)
    arch = evolucionar(Evaluador(v, None, Costos()), np.random.default_rng(1), poblacion=20, generaciones=0,
                       min_operaciones=10, semillas=famosas())
    assert all(E.identificador(e) in arch for e in lista)


def test_supertrend_e_ichimoku_espejo():
    v = velas_aleatorias(1500, semilla=8)
    espejo = v.copy()
    espejo["open"], espejo["close"] = -v["open"], -v["close"]
    espejo["high"], espejo["low"] = -v["low"], -v["high"]
    ctx, ctx_e = E.Contexto(v), E.Contexto(espejo)
    for c in ({"tipo": "cambio_supertrend", "n": 10, "k": 3.0}, {"tipo": "ruptura_nube", "t": 9, "k": 26, "s": 52}):
        largo = E.condicion(ctx, c, 1)
        assert largo.sum() > 3 and (largo == E.condicion(ctx_e, c, -1)).all()


def test_ruptura_rango_exige_consolidacion():
    from tests.conftest import velas
    quieto = [(100, 100.5, 99.5, 100)] * 40          # 40 velas quietas (rango de 1 punto)
    movido = [(100 + (i % 2) * 8, 105 + (i % 2) * 8, 95 + (i % 2) * 8, 100 + (i % 2) * 8) for i in range(40)]
    rompe = [(100, 110, 100, 109)]
    c = {"tipo": "ruptura_rango", "n": 20, "ancho": 4.0}
    s_quieto = E.condicion(E.Contexto(velas(quieto + rompe)), c, 1)
    s_movido = E.condicion(E.Contexto(velas(movido + rompe)), c, 1)
    assert s_quieto[-1] and s_quieto.sum() == 1      # rompe un rango angosto: entra
    assert not s_movido.any()                        # rompe, pero no venía de una consolidación: no entra
    # el espejo: la venta en corto rompe por abajo
    baja = [(100, 100, 90, 91)]
    assert E.condicion(E.Contexto(velas(quieto + baja)), c, -1)[-1]


def test_stop_rango_y_salida_contraria_en_pruebas_y_en_vivo():
    from fabrica.bots import distancia_rango, niveles, senal_contraria
    from fabrica.generador import Evaluador
    from fabrica.motor import Costos
    v = velas_aleatorias(3000, semilla=11)
    est = {"lado": "ambos", "reglas": [{"tipo": "cruce_precio_media", "media": "ema", "n": 20}],
           "salidas": {"stop_tipo": "rango", "stop": 10, "tp_tipo": "ninguno", "tp": 0.0, "trailing": 0.0,
                       "max_velas": 0}}
    ev = Evaluador(v, None, Costos())
    ops = ev.correr(est).operaciones
    assert len(ops) > 20 and set(ops["motivo"]) <= {"stop-loss", "fin de datos"}
    # el riesgo hasta el stop sigue siendo 1 R: ninguna pérdida por stop pasa de ~1 R (más costos y huecos)
    assert ops.loc[ops["motivo"] == "stop-loss", "r"].min() > -1.6
    # la distancia en vivo es la misma que usa la prueba en la última vela
    d_vivo = distancia_rango(est, v, 1)
    d_bt = float(E.Contexto(v).ind("dist_rango", 10, 1).iloc[-1])
    assert d_vivo == pytest.approx(d_bt) and d_vivo > 0
    assert niveles(est["salidas"], 1, 100.0, 1.0, None) is None       # sin distancia no se opera
    assert niveles(est["salidas"], 1, 100.0, 1.0, d_vivo)["dist"] == pytest.approx(d_vivo)
    # salida por señal contraria: aparece como motivo y en vivo usa la misma regla
    est["salidas"]["salida_contraria"] = True
    ops2 = ev.correr(est).operaciones
    assert "señal de salida" in set(ops2["motivo"])
    compra, venta = E.senales_crudas(E.Contexto(v), est)
    i = int(np.flatnonzero(venta)[-1])
    assert senal_contraria(est, v.iloc[: i + 1], 1)
    assert senal_contraria(est, v.iloc[: i + 1], -1) == bool(compra[i])
    est["salidas"].pop("salida_contraria")
    assert not senal_contraria(est, v.iloc[: i + 1], 1)               # si la estrategia no la usa, nunca


def test_sin_mirar_el_futuro_piezas_nuevas():
    """Cortar la historia no cambia las señales ni las distancias ya calculadas (no usan velas futuras)."""
    v = velas_aleatorias(1200, semilla=12)
    corto, largo = E.Contexto(v.iloc[:800]), E.Contexto(v)
    for c in ({"tipo": "ruptura_rango", "n": 20, "ancho": 6.0}, {"tipo": "cambio_supertrend", "n": 10, "k": 3.0},
              {"tipo": "ruptura_nube", "t": 9, "k": 26, "s": 52}, {"tipo": "ruptura_compresion", "n": 20, "m": 50}):
        assert (E.condicion(corto, c, 1) == E.condicion(largo, c, 1)[:800]).all()
    np.testing.assert_allclose(corto.ind("dist_rango", 20, 1), largo.ind("dist_rango", 20, 1)[:800])
