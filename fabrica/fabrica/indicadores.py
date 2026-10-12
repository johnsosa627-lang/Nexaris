"""Indicadores técnicos (numpy/pandas). Todos usan solo datos hasta la vela actual (sin mirar el futuro)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, adjust=False, min_periods=n).mean()


def sma(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=n).mean()


def rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    sube = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    baja = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = sube / baja.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def adx(df: pd.DataFrame, n: int) -> pd.Series:
    up = df["high"].diff()
    dn = -df["low"].diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = atr(df, n)
    pdi = 100 * pd.Series(pdm, index=df.index).ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / a
    ndi = 100 * pd.Series(ndm, index=df.index).ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / a
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def macd_hist(close: pd.Series, f: int = 12, s: int = 26, sig: int = 9) -> pd.Series:
    m = ema(close, f) - ema(close, s)
    return m - ema(m, sig)


def bollinger(close: pd.Series, n: int, k: float):
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std()
    return mid + k * sd, mid, mid - k * sd


def estocastico(df: pd.DataFrame, n: int) -> pd.Series:
    lo = df["low"].rolling(n, min_periods=n).min()
    hi = df["high"].rolling(n, min_periods=n).max()
    return 100 * (df["close"] - lo) / (hi - lo).replace(0, np.nan)


def cci(df: pd.DataFrame, n: int) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    m = sma(tp, n)
    md = tp.rolling(n, min_periods=n).apply(lambda v: np.mean(np.abs(v - v.mean())), raw=True)
    return (tp - m) / (0.015 * md.replace(0, np.nan))


class Cache:
    """Calcula cada indicador una sola vez por set de datos."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.reset_index(drop=True)
        self._c: dict = {}

    def get(self, clave: tuple):
        if clave not in self._c:
            self._c[clave] = self._calc(clave)
        return self._c[clave]

    def _calc(self, k: tuple):
        df, c = self.df, self.df["close"]
        t = k[0]
        if t == "close":
            return c.to_numpy()
        if t == "ema":
            return ema(c, k[1]).to_numpy()
        if t == "sma":
            return sma(c, k[1]).to_numpy()
        if t == "rsi":
            return rsi(c, k[1]).to_numpy()
        if t == "atr":
            return atr(df, k[1]).to_numpy()
        if t == "adx":
            return adx(df, k[1]).to_numpy()
        if t == "macd":
            return macd_hist(c).to_numpy()
        if t == "bb":
            u, m, l = bollinger(c, k[1], k[2])
            return u.to_numpy(), m.to_numpy(), l.to_numpy()
        if t == "max":
            return df["high"].rolling(k[1]).max().shift().to_numpy()
        if t == "min":
            return df["low"].rolling(k[1]).min().shift().to_numpy()
        if t == "volrel":
            return (df["volume"] / sma(df["volume"], k[1])).to_numpy()
        if t == "esto":
            return estocastico(df, k[1]).to_numpy()
        if t == "cci":
            return cci(df, k[1]).to_numpy()
        raise ValueError(f"indicador desconocido {k}")
