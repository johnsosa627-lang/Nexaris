import numpy as np
import pandas as pd
import pytest

from fabrica.indicadores import adx, atr, bollinger, donchian, ema, rsi, sma
from tests.conftest import velas_aleatorias


def wilder_ref(x, n):
    """ewm(alpha=1/n, adjust=False) iterativo, válido desde que hay n valores."""
    out = np.full(len(x), np.nan)
    m, cuenta = np.nan, 0
    for i, v in enumerate(x):
        if np.isnan(v):
            continue
        m = v if np.isnan(m) else m + (v - m) / n
        cuenta += 1
        if cuenta >= n:
            out[i] = m
    return out


def test_atr_contra_referencia():
    v = velas_aleatorias(300)
    h, l, c = v["high"].to_numpy(), v["low"].to_numpy(), v["close"].to_numpy()
    tr = np.array([h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, 300)])
    np.testing.assert_allclose(atr(v["high"], v["low"], v["close"]).to_numpy(), wilder_ref(tr, 14), equal_nan=True)


def test_adx_contra_referencia():
    v = velas_aleatorias(400, semilla=3)
    h, l, c = v["high"].to_numpy(), v["low"].to_numpy(), v["close"].to_numpy()
    tr = np.array([h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, 400)])
    dmp, dmm = [0.0], [0.0]
    for i in range(1, 400):
        up, dn = h[i] - h[i - 1], l[i - 1] - l[i]
        dmp.append(up if up > dn and up > 0 else 0.0)
        dmm.append(dn if dn > up and dn > 0 else 0.0)
    atr_r = wilder_ref(tr, 14)
    dip = 100 * wilder_ref(np.array(dmp), 14) / atr_r
    dim = 100 * wilder_ref(np.array(dmm), 14) / atr_r
    dx = 100 * np.abs(dip - dim) / (dip + dim)
    a, p, m = adx(v["high"], v["low"], v["close"])
    np.testing.assert_allclose(p.to_numpy(), dip, equal_nan=True)
    np.testing.assert_allclose(m.to_numpy(), dim, equal_nan=True)
    np.testing.assert_allclose(a.to_numpy(), wilder_ref(dx, 14), equal_nan=True)
    assert a.dropna().between(0, 100).all()


def test_tendencia_fuerte_da_adx_alto():
    n = 200
    precios = np.linspace(100, 200, n)
    h, l, c = pd.Series(precios + 0.5), pd.Series(precios - 0.5), pd.Series(precios)
    a, p, m = adx(h, l, c)
    assert a.iloc[-1] > 50 and p.iloc[-1] > m.iloc[-1]


def test_donchian_sma_ema_rsi_bollinger():
    s = pd.Series([1, 3, 2, 5, 4, 6, 2], dtype=float)
    alto, bajo = donchian(s, s, 3)
    assert list(alto.dropna()) == [3, 5, 5, 6, 6] and list(bajo.dropna()) == [1, 2, 2, 4, 2]
    assert sma(s, 2).iloc[-1] == 4
    assert ema(s, 3).isna().sum() == 2
    assert rsi(pd.Series(np.arange(50.0))).iloc[-1] == 100
    sup, med, inf = bollinger(pd.Series(np.full(30, 5.0)))
    assert sup.iloc[-1] == inf.iloc[-1] == 5
