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
    arch = evolucionar(Evaluador(v, None, Costos()), np.random.default_rng(1), poblacion=40, generaciones=0,
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


def _velas_15m(desde_utc, n, precio=100.0):
    import pandas as pd
    from tests.conftest import velas
    t0 = int(pd.Timestamp(desde_utc, tz="UTC").timestamp() * 1000)
    return velas([(precio, precio + 0.1, precio - 0.1, precio)] * n, t0=t0, paso=15 * 60_000)


def test_orb_nueva_york_con_horario_de_verano():
    c = {"tipo": "ruptura_apertura", "sesion": "nueva_york", "m": 15}
    # invierno (enero): 9:30 en Nueva York = 14:30 UTC; verano (julio): 13:30 UTC
    for dia, hora_utc in (("2024-01-10", 14), ("2024-07-10", 13)):
        v = _velas_15m(f"{dia} 00:00", 96)
        i_rango = hora_utc * 4 + 2                       # vela de las HH:30 UTC
        v.loc[i_rango, ["high", "low"]] = [101.0, 99.0]  # rango inicial: 99 a 101
        v.loc[i_rango + 3, ["high", "close"]] = [102.0, 101.5]  # 45 minutos después rompe por arriba
        s = E.condicion(E.Contexto(v), c, 1)
        assert s[i_rango + 3] and s.sum() == 1, dia
        assert not E.condicion(E.Contexto(v), c, -1).any()
    # los fines de semana la bolsa de Nueva York no abre
    v = _velas_15m("2024-01-13 00:00", 96)               # sábado
    v.loc[58, ["high", "low"]] = [101.0, 99.0]
    v.loc[61, ["high", "close"]] = [102.0, 101.5]
    assert not E.condicion(E.Contexto(v), c, 1).any()


def test_rango_de_asia_y_sin_mirar_el_futuro():
    c = {"tipo": "ruptura_apertura", "sesion": "asia", "m": 480}
    v = _velas_15m("2024-03-05 00:00", 96)
    v.loc[10, ["high"]] = 101.0                          # máximo de Asia (0 a 8 h UTC)
    v.loc[20, ["low"]] = 98.0
    v.loc[34, ["low", "close"]] = [97.0, 97.5]           # 8:30 UTC rompe por abajo
    assert E.condicion(E.Contexto(v), c, -1)[34] and E.condicion(E.Contexto(v), c, -1).sum() == 1
    # una ruptura antes de que termine el rango no cuenta
    v2 = _velas_15m("2024-03-05 00:00", 96)
    v2.loc[10, ["high", "close"]] = [103.0, 102.5]
    assert not E.condicion(E.Contexto(v2), c, 1)[:32].any()
    # cortar la historia no cambia las señales ya calculadas
    vl = velas_aleatorias(3000, semilla=4, paso=15 * 60_000)
    for ses, m in (("nueva_york", 15), ("londres", 60), ("asia", 480)):
        cc = {"tipo": "ruptura_apertura", "sesion": ses, "m": m}
        corto = E.condicion(E.Contexto(vl.iloc[:1700]), cc, 1)
        assert (corto == E.condicion(E.Contexto(vl), cc, 1)[:1700]).all()


def test_piezas_de_traders_conocidos_a_mano():
    from tests.conftest import velas
    # Turtle Soup: perfora el mínimo de 10 velas y cierra de vuelta adentro
    filas = [(10, 10.5, 9.5, 10)] * 12 + [(10, 10.2, 9.0, 9.8)]
    sopa = E.condicion(E.Contexto(velas(filas)), {"tipo": "sopa_tortuga", "n": 10}, 1)
    assert sopa[12] and sopa.sum() == 1
    # Double 7s: el cierre más bajo de 7 velas
    filas = [(10, 10.5, 9.5, 10 + i * 0.1) for i in range(10)] + [(10, 10.5, 9.0, 9.2)]
    assert E.condicion(E.Contexto(velas(filas)), {"tipo": "extremo_cierres", "n": 7}, 1)[10]
    # vela interior y ruptura de su máximo
    filas = [(10, 12, 8, 10)] * 3 + [(10, 11, 9, 10), (10, 11.5, 9.8, 11.2)]
    interior = E.condicion(E.Contexto(velas(filas)), {"tipo": "barra_interior"}, 1)
    assert interior[4] and interior.sum() == 1


def test_sin_mirar_el_futuro_piezas_de_traders():
    v = velas_aleatorias(1200, semilla=13)
    corto, largo = E.Contexto(v.iloc[:800]), E.Contexto(v)
    for c in ({"tipo": "sopa_tortuga", "n": 20}, {"tipo": "extremo_cierres", "n": 7},
              {"tipo": "ruptura_keltner", "n": 20, "k": 2.0}, {"tipo": "cruce_estocastico", "n": 14, "nivel": 20},
              {"tipo": "barra_interior"}, {"tipo": "cruce_vwap"}):
        assert (E.condicion(corto, c, 1) == E.condicion(largo, c, 1)[:800]).all()
        assert (E.condicion(corto, c, -1) == E.condicion(largo, c, -1)[:800]).all()
