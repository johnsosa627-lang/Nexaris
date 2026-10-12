"""Descarga y guarda velas históricas de Binance Futures (datos públicos)."""
from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DATA_DIR

log = logging.getLogger(__name__)

TF_MS = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def _ruta(simbolo: str, tf: str) -> Path:
    nombre = simbolo.split(":")[0].replace("/", "")
    d = DATA_DIR / "velas"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{nombre}_{tf}.csv"


def cargar(simbolo: str, tf: str) -> pd.DataFrame | None:
    r = _ruta(simbolo, tf)
    if not r.exists():
        return None
    df = pd.read_csv(r)
    return limpiar(df, tf)


def limpiar(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Saca duplicados, ordena y descarta velas con datos inválidos."""
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]
    df = df[df["high"] >= df["low"]].reset_index(drop=True)
    return df


def huecos(df: pd.DataFrame, tf: str) -> int:
    d = np.diff(df["ts"].to_numpy())
    return int((d > TF_MS[tf]).sum())


def actualizar(simbolo: str, tf: str, desde: str, exchange=None) -> pd.DataFrame:
    """Baja solo las velas nuevas y las agrega al archivo. Descarta la vela sin cerrar."""
    import ccxt

    ex = exchange or ccxt.binanceusdm({"enableRateLimit": True})
    viejo = cargar(simbolo, tf)
    if viejo is not None and len(viejo):
        since = int(viejo["ts"].iloc[-1]) + TF_MS[tf]
    else:
        since = int(pd.Timestamp(desde, tz="UTC").timestamp() * 1000)
    filas = []
    ahora = int(time.time() * 1000)
    while since < ahora - TF_MS[tf]:
        lote = ex.fetch_ohlcv(simbolo, tf, since=since, limit=1500)
        if not lote:
            break
        filas.extend(lote)
        nuevo_since = lote[-1][0] + TF_MS[tf]
        if nuevo_since <= since:
            break
        since = nuevo_since
    nuevo = pd.DataFrame(filas, columns=["ts", "open", "high", "low", "close", "volume"])
    # la última vela puede estar abierta todavía: solo velas ya cerradas
    nuevo = nuevo[nuevo["ts"] + TF_MS[tf] <= ahora]
    df = pd.concat([viejo, nuevo]) if viejo is not None else nuevo
    df = limpiar(df, tf)
    df.to_csv(_ruta(simbolo, tf), index=False)
    if huecos(df, tf):
        log.warning("%s %s tiene %d huecos en los datos", simbolo, tf, huecos(df, tf))
    return df


def sintetico(n: int = 5000, semilla: int = 0, tf: str = "1h", tendencia: float = 0.0) -> pd.DataFrame:
    """Velas inventadas (para pruebas y para la línea base anti-suerte)."""
    rng = np.random.default_rng(semilla)
    ret = rng.normal(tendencia, 0.01, n)
    close = 100 * np.exp(np.cumsum(ret))
    return _armar_velas(close, rng, tf)


def _armar_velas(close: np.ndarray, rng, tf: str) -> pd.DataFrame:
    n = len(close)
    open_ = np.r_[close[0], close[:-1]]
    rango = np.abs(rng.normal(0, 0.004, n)) * close
    high = np.maximum(open_, close) + rango
    low = np.minimum(open_, close) - rango
    vol = rng.lognormal(10, 0.5, n)
    ts = 1_600_000_000_000 + np.arange(n) * TF_MS[tf]
    return pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low, "close": close, "volume": vol})


def barajar(df: pd.DataFrame, semilla: int, tf: str = "1h") -> pd.DataFrame:
    """Mismos movimientos que el mercado real pero en orden al azar: mata cualquier patrón real
    y deja la misma volatilidad. Sirve para medir cuánto 'gana' la pura suerte."""
    rng = np.random.default_rng(semilla)
    c = df["close"].to_numpy()
    r = np.diff(np.log(c))
    rng.shuffle(r)
    close = c[0] * np.exp(np.r_[0, np.cumsum(r)])
    rel_h = (df["high"] / df["close"]).to_numpy()
    rel_l = (df["low"] / df["close"]).to_numpy()
    idx = rng.permutation(len(c))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(np.maximum(open_, close), close * rel_h[idx])
    low = np.minimum(np.minimum(open_, close), close * rel_l[idx])
    vol = df["volume"].to_numpy()[idx]
    return pd.DataFrame({"ts": df["ts"].to_numpy(), "open": open_, "high": high, "low": low,
                         "close": close, "volume": vol})
