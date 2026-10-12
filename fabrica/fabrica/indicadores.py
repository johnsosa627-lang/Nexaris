"""Indicadores técnicos (pandas). Todos usan solo datos hasta la vela actual inclusive."""
import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def wilder(s: pd.Series, n: int) -> pd.Series:
    """Media suavizada de Wilder (usada por RSI, ATR y ADX)."""
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    g = wilder(delta.clip(lower=0), n)
    p = wilder(-delta.clip(upper=0), n)
    r = 100 - 100 / (1 + g / p)
    r = r.where(p != 0, 100.0).where(~((g == 0) & (p == 0)), 50.0)
    r[g.isna()] = np.nan
    return r


def macd(close: pd.Series, rapida: int = 12, lenta: int = 26, senal: int = 9):
    linea = close.ewm(span=rapida, adjust=False).mean() - close.ewm(span=lenta, adjust=False).mean()
    sen = linea.ewm(span=senal, adjust=False).mean()
    return linea, sen, linea - sen


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0):
    media = close.rolling(n).mean()
    desvio = close.rolling(n).std(ddof=0)
    return media + k * desvio, media, media - k * desvio


def rango_verdadero(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev = close.shift(1)
    return pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    return wilder(rango_verdadero(high, low, close), n)


def adx(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14):
    """Devuelve (ADX, +DI, -DI)."""
    sube = high.diff()
    baja = -low.diff()
    dm_mas = pd.Series(np.where((sube > baja) & (sube > 0), sube, 0.0), index=high.index)
    dm_menos = pd.Series(np.where((baja > sube) & (baja > 0), baja, 0.0), index=high.index)
    tr = wilder(rango_verdadero(high, low, close), n)
    di_mas = 100 * wilder(dm_mas, n) / tr
    di_menos = 100 * wilder(dm_menos, n) / tr
    suma = di_mas + di_menos
    dx = 100 * (di_mas - di_menos).abs() / suma.where(suma != 0)
    return wilder(dx, n), di_mas, di_menos


def donchian(high: pd.Series, low: pd.Series, n: int = 20):
    """Máximo y mínimo de las últimas n velas (incluye la actual)."""
    return high.rolling(n).max(), low.rolling(n).min()
