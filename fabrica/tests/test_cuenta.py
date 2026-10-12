import numpy as np
import pytest

from fabrica import cuenta as C


def test_capital_nunca_sube_solo():
    assert C.capital_base(15, 40) == 15  # ganó, pero el riesgo se sigue calculando sobre 15
    assert C.capital_base(15, 12) == 12  # perdió: arriesga menos
    assert C.capital_base(15, -1) == 0


def test_tamano_y_minimos():
    # 1% de 15 = 0,15 USDT de riesgo; stop a 0,01 por unidad => 15 unidades; a 0,5 => 7,5 USDT
    q, motivo = C.tamano(0.15, 0.01, 0.5, 15, 3, lambda x: round(x, 1), 0.1, 5)
    assert q == pytest.approx(15) and motivo == ""
    # tope de apalancamiento: 3x de 15 = 45 USDT
    q, _ = C.tamano(0.15, 0.0001, 0.5, 15, 3)
    assert q * 0.5 == pytest.approx(45)
    q, motivo = C.tamano(0.15, 0.05, 0.5, 15, 3, None, 0.1, 5)  # 3 unidades = 1,5 USDT < 5
    assert q == 0 and "Binance exige" in motivo
    q, motivo = C.tamano(0.15, 1000, 60000, 15, 3, lambda x: round(x, 3), 0.001, 100)  # BTC con 15 USDT
    assert q == 0 and motivo
    q, motivo = C.tamano(0.15, 1.0, 100, 15, 3, None, 0.1, 500)
    assert q == 0 and "Binance exige al menos 500" in motivo


def test_riesgo_abierto():
    assert C.riesgo_abierto_permitido(0.30, 0.15, 15, 3)
    assert not C.riesgo_abierto_permitido(0.45, 0.15, 15, 3)


def test_frenos():
    assert C.freno_diario(-0.45, 0, 15, 3, 2)          # perdió 3% del día
    assert C.freno_diario(-0.10, 2, 15, 3, 2)          # 2 perdidas seguidas
    assert C.freno_diario(-0.10, 1, 15, 3, 2) is None
    assert C.freno_total(12.75, 15, 15) and not C.freno_total(12.8, 15, 15)


def test_estadistica():
    assert C.drawdown_pct([0.01, -0.02, -0.01, 0.05]) == pytest.approx(3.0)
    bt = np.random.default_rng(0).normal(0.003, 0.01, 500)
    assert abs(C.z_contra_backtest(bt[:50], bt)) < 2
    assert C.z_contra_backtest([-0.01] * 30, bt) < -5
    assert C.t_welch([0.02] * 15 + [0.01] * 15, [0.0] * 15 + [0.01] * 15) > 2
    assert C.t_welch([0.0, 0.0], [0.0, 0.0]) == 0


def test_correlacion():
    dias = [f"2024-01-{d:02d}" for d in range(1, 31)]
    rng = np.random.default_rng(1)
    a = dict(zip(dias, rng.normal(0, 1, 30)))
    assert C.correlacion(a, a) == pytest.approx(1)
    assert C.correlacion(a, {d: -v for d, v in a.items()}) == pytest.approx(-1)
    assert abs(C.correlacion(a, dict(zip(dias, rng.normal(0, 1, 30))))) < 0.5
    assert C.correlacion(a, {}) == 0
