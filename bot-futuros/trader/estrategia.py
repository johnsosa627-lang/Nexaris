"""Reglas de entrada: solo se evalúan velas cerradas."""
from typing import Optional

import pandas as pd

COLUMNAS_NECESARIAS = ["ema9", "ema21", "rsi", "macd_hist", "bb_sup", "bb_inf", "vol_media"]

_UNIDADES_MS = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}


def timeframe_a_ms(timeframe: str) -> int:
    return int(timeframe[:-1]) * _UNIDADES_MS[timeframe[-1]]


def velas_cerradas(df: pd.DataFrame, timeframe: str, ahora_ms: int) -> pd.DataFrame:
    """Descarta la vela en formación (la que todavía no terminó)."""
    duracion = timeframe_a_ms(timeframe)
    return df[df["ts"] + duracion <= ahora_ms].reset_index(drop=True)


def condiciones(df: pd.DataFrame) -> dict:
    """Detalle de cada condición sobre la última vela cerrada (útil para logs y tests)."""
    if len(df) < 2:
        return {}
    act, prev = df.iloc[-1], df.iloc[-2]
    if act[COLUMNAS_NECESARIAS].isna().any() or prev[["ema9", "ema21"]].isna().any():
        return {}
    return {
        "cruce_alcista": prev["ema9"] <= prev["ema21"] and act["ema9"] > act["ema21"],
        "cruce_bajista": prev["ema9"] >= prev["ema21"] and act["ema9"] < act["ema21"],
        "rsi_long": 50 <= act["rsi"] <= 70,
        "rsi_short": 30 <= act["rsi"] <= 50,
        "macd_pos": act["macd_hist"] > 0,
        "macd_neg": act["macd_hist"] < 0,
        "bajo_bb_sup": act["close"] < act["bb_sup"],
        "sobre_bb_inf": act["close"] > act["bb_inf"],
        "volumen_alto": act["volume"] > act["vol_media"],
    }


def evaluar_senal(df: pd.DataFrame) -> Optional[str]:
    """Devuelve 'LONG', 'SHORT' o None según la última vela cerrada del DataFrame."""
    c = condiciones(df)
    if not c:
        return None
    if c["cruce_alcista"] and c["rsi_long"] and c["macd_pos"] and c["bajo_bb_sup"] and c["volumen_alto"]:
        return "LONG"
    if c["cruce_bajista"] and c["rsi_short"] and c["macd_neg"] and c["sobre_bb_inf"] and c["volumen_alto"]:
        return "SHORT"
    return None
