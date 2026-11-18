"""Clima del mercado: ¿Bitcoin está en tendencia alcista, bajista o de costado?

Se mide con las velas de 4 horas de Bitcoin (el líder que arrastra a todo el mercado), solo con velas ya
cerradas:
- alcista: hay tendencia (ADX de 14 >= umbral) y el precio está por encima de su media exponencial de 200;
- bajista: hay tendencia y el precio está por debajo de esa media;
- lateral: no hay tendencia clara (ADX bajo).

Sirve para que cada bot opere solo en el clima en el que demostró ganar: en sus pruebas de 5 años (cada
operación se clasifica por el clima que había al entrar) y en vivo.
"""
from typing import Optional

import numpy as np
import pandas as pd

from . import indicadores as ind

CLIMAS = ("alcista", "bajista", "lateral")
PASO_4H = 4 * 3600 * 1000
ICONO = {"alcista": "📈", "bajista": "📉", "lateral": "↔️"}


def serie_clima(velas_btc_4h: pd.DataFrame, adx_min: float = 20, ema_n: int = 200) -> pd.Series:
    """Clima al CERRAR cada vela de 4 h. El índice es el momento en que se conoce (cierre de la vela)."""
    v = velas_btc_4h.reset_index(drop=True)
    if len(v) == 0:
        return pd.Series(dtype=object)
    adx, _, _ = ind.adx(v["high"], v["low"], v["close"], 14)
    ema = ind.ema(v["close"], ema_n)
    tendencia = (adx >= adx_min).to_numpy()
    arriba = (v["close"] > ema).to_numpy()
    valido = (adx.notna() & ema.notna()).to_numpy()
    clima = np.where(~valido, None, np.where(~tendencia, "lateral", np.where(arriba, "alcista", "bajista")))
    return pd.Series(clima, index=(v["ts"].astype("int64") + PASO_4H).to_numpy())


def clima_en(ts_ms, serie: pd.Series):
    """Clima vigente en cada momento `ts_ms` (el de la última vela de 4 h ya cerrada). Acepta un número o un array."""
    if len(serie) == 0:
        return None if np.isscalar(ts_ms) else np.full(len(ts_ms), None, dtype=object)
    idx = np.searchsorted(serie.index.to_numpy(), np.asarray(ts_ms, dtype="int64"), side="right") - 1
    valores = serie.to_numpy()
    if np.isscalar(ts_ms):
        return valores[idx] if idx >= 0 else None
    return np.array([valores[i] if i >= 0 else None for i in idx], dtype=object)


def clima_actual(velas_btc_4h: pd.DataFrame, ahora_ms: int, adx_min: float = 20, ema_n: int = 200) -> Optional[str]:
    return clima_en(int(ahora_ms), serie_clima(velas_btc_4h, adx_min, ema_n))


def stats_por_clima(ops: pd.DataFrame, serie: pd.Series) -> dict:
    """{clima: {"n": operaciones, "r": R promedio}} de un backtest, según el clima al momento de entrar."""
    if ops is None or len(ops) == 0 or len(serie) == 0:
        return {}
    climas = clima_en(ops["entrada_ts"].to_numpy(dtype="int64"), serie)
    r = ops["r"].to_numpy(dtype=float)
    salida = {}
    for c in CLIMAS:
        m = climas == c
        if m.any():
            salida[c] = {"n": int(m.sum()), "r": round(float(r[m].mean()), 4)}
    return salida
