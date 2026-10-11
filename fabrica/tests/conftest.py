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
