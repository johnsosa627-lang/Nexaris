import numpy as np
import pandas as pd

from trader.indicadores import bollinger, ema, macd, rsi


def rsi_referencia(precios, n=14):
    """Implementación iterativa clásica de Wilder."""
    deltas = np.diff(precios)
    resultado = [np.nan] * len(precios)
    ganancias = np.where(deltas > 0, deltas, 0.0)
    perdidas = np.where(deltas < 0, -deltas, 0.0)
    # media de Wilder sembrada con EMA(alpha=1/n) desde el primer delta (equivalente a pandas ewm adjust=False)
    g, p = ganancias[0], perdidas[0]
    for i in range(1, len(deltas)):
        g = g + (ganancias[i] - g) / n
        p = p + (perdidas[i] - p) / n
        if i + 1 >= n:
            resultado[i + 1] = 100.0 if p == 0 else 100 - 100 / (1 + g / p)
    return np.array(resultado)


def test_ema_coincide_con_recursion_manual():
    s = pd.Series([1, 2, 3, 2, 5, 8, 7, 6, 9, 10], dtype=float)
    alpha = 2 / (9 + 1)
    esperado = [s[0]]
    for x in s[1:]:
        esperado.append(alpha * x + (1 - alpha) * esperado[-1])
    assert np.allclose(ema(s, 9).values, esperado)


def test_rsi_coincide_con_wilder_iterativo():
    rng = np.random.default_rng(1)
    precios = 100 + np.cumsum(rng.normal(0, 1, 200))
    calculado = rsi(pd.Series(precios), 14).values
    referencia = rsi_referencia(precios, 14)
    mascara = ~np.isnan(referencia)
    assert np.allclose(calculado[mascara], referencia[mascara], atol=1e-9)
    assert np.isnan(calculado[:14]).all()


def test_rsi_extremos():
    sube = pd.Series(np.arange(1, 60, dtype=float))
    baja = pd.Series(np.arange(60, 1, -1, dtype=float))
    plano = pd.Series(np.full(60, 5.0))
    assert rsi(sube).iloc[-1] == 100
    assert rsi(baja).iloc[-1] == 0
    assert rsi(plano).iloc[-1] == 50
    r = rsi(pd.Series(100 + np.cumsum(np.random.default_rng(3).normal(0, 1, 300))))
    assert r.dropna().between(0, 100).all()


def test_macd_constante_y_tendencia():
    plano = pd.Series(np.full(100, 3.0))
    _, _, hist = macd(plano)
    assert np.allclose(hist, 0)
    acelera = pd.Series(np.exp(np.linspace(0, 1, 100)))
    linea, _, hist = macd(acelera)
    assert linea.iloc[-1] > 0 and hist.iloc[-1] > 0


def test_bollinger():
    plano = pd.Series(np.full(40, 2.0))
    sup, media, inf = bollinger(plano)
    assert np.allclose(sup.dropna(), 2.0) and np.allclose(inf.dropna(), 2.0)
    s = pd.Series(np.random.default_rng(2).normal(10, 1, 60))
    sup, media, inf = bollinger(s, 20, 2)
    ventana = s.iloc[-20:].values
    assert np.isclose(media.iloc[-1], ventana.mean())
    assert np.isclose(sup.iloc[-1], ventana.mean() + 2 * ventana.std(ddof=0))
    assert np.isclose(inf.iloc[-1], ventana.mean() - 2 * ventana.std(ddof=0))
