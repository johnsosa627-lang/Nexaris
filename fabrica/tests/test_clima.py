"""Clima del mercado: clasificación de Bitcoin 4 h y freno de titulares en el clima donde no ganan."""
import numpy as np
import pandas as pd

from fabrica.clima import clima_actual, clima_en, serie_clima, stats_por_clima
from tests.test_vivo import EjecutorFalso, Liga, MercadoFalso, cfg_prueba, distinta

H4 = 4 * 3600 * 1000


def btc(pasos):
    """Velas de 4 h con un camino de precio dado (tendencias limpias para el ADX)."""
    c = 100 * np.exp(np.cumsum(pasos))
    o = np.concatenate([[100.0], c[:-1]])
    return pd.DataFrame({"ts": np.arange(len(c), dtype="int64") * H4, "open": o, "high": np.maximum(o, c) * 1.001,
                         "low": np.minimum(o, c) * 0.999, "close": c, "volume": 1.0})


def test_clasifica_alcista_bajista_y_lateral():
    rng = np.random.default_rng(1)
    sube = btc(np.full(600, 0.004) + rng.normal(0, 0.001, 600))
    baja = btc(np.full(600, -0.004) + rng.normal(0, 0.001, 600))
    quieto = btc(np.tile([0.003, -0.003], 300) + np.random.default_rng(4).normal(0, 0.0005, 600))  # ADX bajo
    fin = 600 * H4
    assert clima_actual(sube, fin) == "alcista"
    assert clima_actual(baja, fin) == "bajista"
    assert clima_actual(quieto, fin) == "lateral"


def test_sin_mirar_el_futuro_y_por_operacion():
    v = btc(np.concatenate([np.full(400, 0.004), np.full(400, -0.004)]))
    s = serie_clima(v)
    # la vela k se conoce recién al cerrar: en su apertura todavía vale el clima anterior
    assert clima_en(int(v["ts"].iloc[300]), s) == s.iloc[299]
    assert clima_en(-1, s) is None
    ops = pd.DataFrame({"entrada_ts": [int(v["ts"].iloc[350]), int(v["ts"].iloc[790])], "r": [2.0, -1.0]})
    st = stats_por_clima(ops, s)
    assert st["alcista"] == {"n": 1, "r": 2.0} and st["bajista"] == {"n": 1, "r": -1.0}


def armar(tmp_path, por_clima, clima="alcista"):
    mensajes = []
    t = {"ahora": 1_700_000_000.0}
    cfg = cfg_prueba()
    cfg["clima"] = {"activo": True, "min_ops_pruebas": 20, "min_ops_vivo": 5}
    liga = Liga(cfg, str(tmp_path), MercadoFalso(), EjecutorFalso(), mensajes.append, reloj=lambda: t["ahora"],
                modo="testnet")
    liga.sincronizar_banco([{**distinta(1), "por_clima": por_clima}])
    liga.completar_titulares()
    liga.actualizar_clima(clima)
    return liga, liga.e["bots"]["bot1"], mensajes


VELA = {"ts": 0, "open": 100, "high": 100.5, "low": 99.5, "close": 100}


def test_titular_no_entra_en_el_clima_donde_perdia_en_sus_pruebas(tmp_path):
    liga, bot, _ = armar(tmp_path, {"alcista": {"n": 40, "r": -0.3}, "bajista": {"n": 60, "r": 0.5}})
    liga._abrir(bot, 1, 0.5, VELA)
    assert bot["posicion"] is None and "clima alcista" in bot["senales_perdidas"][-1]["motivo"]
    liga.actualizar_clima("bajista")
    liga._abrir(bot, -1, 0.5, VELA)
    assert bot["posicion"] is not None and bot["posicion"]["clima"] == "bajista"
    liga._cerrar(bot, "prueba")
    assert bot["trades"][-1]["clima"] == "bajista"


def test_pocas_pruebas_no_frenan_y_lo_vivido_manda(tmp_path):
    liga, bot, _ = armar(tmp_path, {"alcista": {"n": 5, "r": -1.0}})   # muy pocas: no alcanza para frenar
    assert liga.no_gana_en_este_clima(bot) is None
    bot["trades"] = [{"r": -1.0, "clima": "alcista", "fecha": "x", "rol": "titular", "pnl_usdt": -1}] * 5
    assert "en vivo pierde" in liga.no_gana_en_este_clima(bot)
    bot["trades"] += [{"r": 3.0, "clima": "alcista", "fecha": "x", "rol": "titular", "pnl_usdt": 3}] * 3
    assert liga.no_gana_en_este_clima(bot) is None


def test_aviso_al_cambiar_el_clima_y_comando(tmp_path):
    liga, bot, mensajes = armar(tmp_path, {"lateral": {"n": 30, "r": -0.2}})
    liga.actualizar_clima("lateral")
    assert any("Cambió el clima del mercado: de alcista a" in m and bot["id"] in m for m in mensajes)
    texto = liga.texto_clima()
    assert "LATERAL" in texto and "⛔" in texto
    assert "Clima del mercado" in liga.texto_estado()
