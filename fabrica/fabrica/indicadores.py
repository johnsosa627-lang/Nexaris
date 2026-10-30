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


def supertrend(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 10, k: float = 3.0) -> pd.Series:
    """Dirección del Supertrend: +1 alcista, -1 bajista, NaN mientras no hay datos."""
    a = atr(high, low, close, n).to_numpy()
    medio = ((high + low) / 2).to_numpy()
    c = close.to_numpy()
    sup_b, inf_b = medio + k * a, medio - k * a
    direccion = np.full(len(c), np.nan)
    sup = inf = np.nan
    d = 0
    for i in range(len(c)):
        if np.isnan(a[i]):
            continue
        if d == 0:
            sup, inf, d = sup_b[i], inf_b[i], (1 if c[i] > medio[i] else -1)
        else:
            sup = sup_b[i] if (sup_b[i] < sup or c[i - 1] > sup) else sup
            inf = inf_b[i] if (inf_b[i] > inf or c[i - 1] < inf) else inf
            if d == 1 and c[i] < inf:
                d = -1
            elif d == -1 and c[i] > sup:
                d = 1
        direccion[i] = d
    return pd.Series(direccion, index=close.index)


def ichimoku_nube(high: pd.Series, low: pd.Series, t: int = 9, k: int = 26, s: int = 52):
    """(techo, piso) de la nube de Ichimoku que corresponde a la vela actual (calculada con datos de hace k velas)."""
    tenkan = (high.rolling(t).max() + low.rolling(t).min()) / 2
    kijun = (high.rolling(k).max() + low.rolling(k).min()) / 2
    a = ((tenkan + kijun) / 2).shift(k)
    b = ((high.rolling(s).max() + low.rolling(s).min()) / 2).shift(k)
    return pd.concat([a, b], axis=1).max(axis=1, skipna=False), pd.concat([a, b], axis=1).min(axis=1, skipna=False)


def estocastico(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14, d: int = 3):
    """Estocástico lento: %K (dónde cerró dentro del rango de n velas, 0-100) y %D (su media de d velas)."""
    bajo, alto = low.rolling(n).min(), high.rolling(n).max()
    k = 100 * (close - bajo) / (alto - bajo).replace(0, np.nan)
    return k, k.rolling(d).mean()


def vwap_diario(high: pd.Series, low: pd.Series, close: pd.Series, volumen: pd.Series, ts: pd.Series) -> pd.Series:
    """Precio promedio ponderado por volumen desde las 0 h UTC de cada día (se reinicia cada día)."""
    tipico = (high + low + close) / 3
    dia = (ts.astype("int64") // 86_400_000)
    return (tipico * volumen).groupby(dia).cumsum() / volumen.groupby(dia).cumsum().replace(0, np.nan)
