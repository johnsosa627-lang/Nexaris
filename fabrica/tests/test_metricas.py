import numpy as np
import pandas as pd
import pytest

from fabrica.metricas import calcular_metricas, curva_capital, estabilidad, explicar, max_drawdown_pct

DIA = 86_400_000
T0 = 1_609_459_200_000


def ops(retornos, r=None, dias=None):
    n = len(retornos)
    dias = dias if dias is not None else list(range(1, n + 1))
    return pd.DataFrame({"salida_ts": [T0 + d * DIA for d in dias], "retorno": retornos,
                         "r": r if r is not None else np.array(retornos) * 100, "velas": [5] * n})


def test_metricas_basicas():
    m = calcular_metricas(ops([0.02, -0.01, 0.02, -0.01]), T0, T0 + 365 * DIA)
    assert m["operaciones"] == 4 and m["ganadoras_pct"] == 50
    assert m["profit_factor"] == pytest.approx(2.0)
    final = 1.02 * 0.99 * 1.02 * 0.99
    assert m["retorno_pct"] == pytest.approx((final - 1) * 100)
    assert m["max_drawdown_pct"] == pytest.approx(1.0)
    assert m["ret_dd"] == pytest.approx(m["retorno_pct"] / 1.0)
    assert m["expectativa_r"] == pytest.approx(0.5)
    assert m["racha_perdedora"] == 1


def test_drawdown_y_curva():
    curva = curva_capital([0.1, -0.2, 0.05])
    assert curva == pytest.approx([1, 1.1, 0.88, 0.924])
    assert max_drawdown_pct(curva) == pytest.approx(20.0)


def test_estabilidad():
    t = np.arange(50)
    assert estabilidad(1.01 ** t, t) == pytest.approx(1.0)
    assert estabilidad(0.99 ** t, t) == pytest.approx(-1.0)
    ruido = np.exp(np.cumsum(np.random.default_rng(0).normal(0, 0.05, 50)))
    assert abs(estabilidad(ruido, t)) < 0.9


def test_anios_y_sin_perdidas():
    o = ops([0.01, 0.01, -0.005], dias=[10, 20, 400])
    m = calcular_metricas(o, T0, T0 + 500 * DIA)
    assert set(m["anios"]) == {2021, 2022}
    assert m["anios"][2021] == pytest.approx((1.01 * 1.01 - 1) * 100, abs=0.01)
    assert m["anios_positivos_pct"] == 50
    m = calcular_metricas(ops([0.01, 0.02]), T0, T0 + 10 * DIA)
    assert m["profit_factor"] == 999 and m["ret_dd"] == 999


def test_sin_operaciones_y_explicacion():
    m = calcular_metricas(ops([]), T0, T0)
    assert m["operaciones"] == 0
    assert "ninguna" in explicar(m)
    texto = explicar(calcular_metricas(ops([0.02, -0.01]), T0, T0 + 30 * DIA))
    assert "15 dólares" in texto and "profit factor" in texto
