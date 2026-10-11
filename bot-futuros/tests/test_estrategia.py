import numpy as np
import pandas as pd
import pytest

from tests.conftest import T0, TF_MS, buscar_senal, velas_sinteticas
from trader.estrategia import condiciones, evaluar_senal, timeframe_a_ms, velas_cerradas
from trader.indicadores import agregar_indicadores, ohlcv_a_dataframe

BASE_LONG = [
    dict(ema9=1.00, ema21=1.01, rsi=48, macd_hist=-0.1, bb_sup=1.2, bb_inf=0.8, close=1.0, volume=100, vol_media=100),
    dict(ema9=1.02, ema21=1.01, rsi=60, macd_hist=0.05, bb_sup=1.2, bb_inf=0.8, close=1.05, volume=150, vol_media=100),
]
BASE_SHORT = [
    dict(ema9=1.02, ema21=1.01, rsi=52, macd_hist=0.1, bb_sup=1.2, bb_inf=0.8, close=1.0, volume=100, vol_media=100),
    dict(ema9=1.00, ema21=1.01, rsi=40, macd_hist=-0.05, bb_sup=1.2, bb_inf=0.8, close=0.95, volume=150, vol_media=100),
]


def armar(filas, **cambios_ultima):
    filas = [dict(f) for f in filas]
    filas[-1].update(cambios_ultima)
    return pd.DataFrame(filas)


def test_timeframes():
    assert timeframe_a_ms("15m") == 900_000
    assert timeframe_a_ms("1h") == 3_600_000
    assert timeframe_a_ms("4h") == 14_400_000


def test_velas_cerradas_descarta_la_vela_en_formacion():
    df = ohlcv_a_dataframe(velas_sinteticas(10))
    ahora = T0 + 9 * TF_MS + 60_000  # un minuto dentro de la vela 9
    cerradas = velas_cerradas(df, "15m", ahora)
    assert len(cerradas) == 9 and cerradas["ts"].iloc[-1] == T0 + 8 * TF_MS
    justo = velas_cerradas(df, "15m", T0 + 10 * TF_MS)
    assert len(justo) == 10


def test_long_valida():
    assert evaluar_senal(armar(BASE_LONG)) == "LONG"


def test_short_valida():
    assert evaluar_senal(armar(BASE_SHORT)) == "SHORT"


@pytest.mark.parametrize("cambio", [
    dict(ema9=1.005),          # sin cruce (sigue debajo)
    dict(rsi=49.9), dict(rsi=70.1),
    dict(macd_hist=0.0), dict(macd_hist=-0.01),
    dict(close=1.2), dict(close=1.3),  # en/arriba de la Bollinger superior
    dict(volume=100), dict(volume=90),  # volumen no supera la media
])
def test_long_rechazada_si_falla_una_condicion(cambio):
    assert evaluar_senal(armar(BASE_LONG, **cambio)) is None


@pytest.mark.parametrize("cambio", [
    dict(ema9=1.015),
    dict(rsi=29.9), dict(rsi=50.1),
    dict(macd_hist=0.0), dict(macd_hist=0.01),
    dict(close=0.8), dict(close=0.7),
    dict(volume=100),
])
def test_short_rechazada_si_falla_una_condicion(cambio):
    assert evaluar_senal(armar(BASE_SHORT, **cambio)) is None


def test_cruce_previo_no_repite_senal():
    filas = [dict(BASE_LONG[1]), dict(BASE_LONG[1])]  # ya estaba arriba en la vela anterior
    assert evaluar_senal(pd.DataFrame(filas)) is None


def test_nan_no_genera_senal():
    assert evaluar_senal(armar(BASE_LONG, rsi=np.nan)) is None
    assert evaluar_senal(armar(BASE_LONG[:1])) is None


def test_senales_en_datos_sinteticos_cumplen_todas_las_reglas():
    encontrados = {"LONG": 0, "SHORT": 0}
    for semilla in range(40):
        df = agregar_indicadores(ohlcv_a_dataframe(velas_sinteticas(300, semilla)))
        for i in range(60, len(df)):
            ventana = df.iloc[: i + 1]
            lado = evaluar_senal(ventana)
            if not lado:
                continue
            encontrados[lado] += 1
            a, p = ventana.iloc[-1], ventana.iloc[-2]
            assert a["volume"] > a["vol_media"]
            if lado == "LONG":
                assert p["ema9"] <= p["ema21"] and a["ema9"] > a["ema21"]
                assert 50 <= a["rsi"] <= 70 and a["macd_hist"] > 0 and a["close"] < a["bb_sup"]
            else:
                assert p["ema9"] >= p["ema21"] and a["ema9"] < a["ema21"]
                assert 30 <= a["rsi"] <= 50 and a["macd_hist"] < 0 and a["close"] > a["bb_inf"]
    assert encontrados["LONG"] > 0 and encontrados["SHORT"] > 0


def test_buscar_senal_helper():
    velas, i = buscar_senal("LONG")
    df = agregar_indicadores(ohlcv_a_dataframe(velas[: i + 1]))
    assert evaluar_senal(df) == "LONG"
    assert condiciones(df)["cruce_alcista"]
