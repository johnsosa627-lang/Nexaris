"""Indicadores técnicos calculados con pandas (sin librerías externas)."""
import numpy as np
import pandas as pd


def ema(serie: pd.Series, periodo: int) -> pd.Series:
    return serie.ewm(span=periodo, adjust=False).mean()


def rsi(serie: pd.Series, periodo: int = 14) -> pd.Series:
    """RSI con suavizado de Wilder."""
    delta = serie.diff()
    ganancia = delta.clip(lower=0)
    perdida = -delta.clip(upper=0)
    media_g = ganancia.ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()
    media_p = perdida.ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()
    rs = media_g / media_p
    resultado = 100 - 100 / (1 + rs)
    # Sin pérdidas en el período -> RSI 100; sin movimiento -> 50
    resultado = resultado.where(media_p != 0, 100.0)
    resultado = resultado.where(~((media_g == 0) & (media_p == 0)), 50.0)
    resultado[media_g.isna()] = np.nan
    return resultado


def macd(serie: pd.Series, rapida: int = 12, lenta: int = 26, senal: int = 9):
    linea = ema(serie, rapida) - ema(serie, lenta)
    linea_senal = ema(linea, senal)
    return linea, linea_senal, linea - linea_senal


def bollinger(serie: pd.Series, periodo: int = 20, desvios: float = 2.0):
    media = serie.rolling(periodo).mean()
    desvio = serie.rolling(periodo).std(ddof=0)
    return media + desvios * desvio, media, media - desvios * desvio


def agregar_indicadores(df: pd.DataFrame) -> pd.DataFrame:
    """Recibe columnas ts, open, high, low, close, volume y agrega los indicadores."""
    df = df.copy()
    df["ema9"] = ema(df["close"], 9)
    df["ema21"] = ema(df["close"], 21)
    df["rsi"] = rsi(df["close"], 14)
    df["macd"], df["macd_senal"], df["macd_hist"] = macd(df["close"])
    df["bb_sup"], df["bb_media"], df["bb_inf"] = bollinger(df["close"], 20, 2.0)
    df["vol_media"] = df["volume"].rolling(20).mean()
    return df


def ohlcv_a_dataframe(velas: list) -> pd.DataFrame:
    df = pd.DataFrame(velas, columns=["ts", "open", "high", "low", "close", "volume"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["ts"] = df["ts"].astype("int64")
    return df
