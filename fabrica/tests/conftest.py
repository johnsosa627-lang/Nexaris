import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

H = 3_600_000
T0 = 1_609_459_200_000  # 2021-01-01 00:00 UTC


def velas(filas, t0=T0, paso=H):
    """filas: lista de (open, high, low, close)."""
    df = pd.DataFrame(filas, columns=["open", "high", "low", "close"], dtype=float)
    df.insert(0, "ts", t0 + np.arange(len(df), dtype="int64") * paso)
    df["volume"] = 1000.0
    return df


def velas_aleatorias(n=2000, semilla=0, precio=100.0, vol=0.01, paso=H, t0=T0):
    rng = np.random.default_rng(semilla)
    filas, c = [], precio
    for _ in range(n):
        o = c
        c = o * math.exp(rng.normal(0, vol))
        h = max(o, c) * (1 + abs(rng.normal(0, vol / 2)))
        l = min(o, c) * (1 - abs(rng.normal(0, vol / 2)))
        filas.append((o, h, l, c))
    df = velas(filas, t0, paso)
    df["volume"] = rng.lognormal(10, 0.5, n)
    return df


def serie_mercado(n=20000, semilla=0, phi=0.0, vol=0.006, paso=H, t0=T0):
    """Velas sintéticas. phi > 0 = los movimientos tienden a continuar (tendencias reales, aprovechables)."""
    rng = np.random.default_rng(semilla)
    ruido = rng.normal(0, vol, n)
    r = np.empty(n)
    r[0] = ruido[0]
    for i in range(1, n):
        r[i] = phi * r[i - 1] + ruido[i]
    c = 100 * np.exp(np.cumsum(r))
    o = np.concatenate([[100.0], c[:-1]])
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, vol / 3, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, vol / 3, n)))
    df = pd.DataFrame({"ts": t0 + np.arange(n, dtype="int64") * paso, "open": o, "high": h, "low": l, "close": c,
                       "volume": rng.lognormal(10, 0.4, n)})
    return df


def agrupar(df, factor):
    """Pasa velas a una temporalidad mayor (ej: 1h -> 4h con factor 4)."""
    g = np.arange(len(df)) // factor
    out = df.groupby(g).agg(ts=("ts", "first"), open=("open", "first"), high=("high", "max"),
                            low=("low", "min"), close=("close", "last"), volume=("volume", "sum"))
    return out.iloc[: len(df) // factor].reset_index(drop=True)


def escribir_mercados(carpeta, simbolos, phi, n=20000, semilla=0):
    import os
    from fabrica import datos
    for i, s in enumerate(simbolos):
        v1 = serie_mercado(n, semilla + i, phi)
        for tf, df in (("1h", v1), ("4h", agrupar(v1, 4))):
            ruta = datos.ruta_velas(carpeta, s, tf)
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            df.to_csv(ruta, index=False, compression="gzip")
