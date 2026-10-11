import pytest

from trader import riesgo


def test_niveles_long_y_short():
    sl, tp = riesgo.calcular_niveles("LONG", 100.0, 3, 6)
    assert sl == pytest.approx(97.0) and tp == pytest.approx(106.0)
    sl, tp = riesgo.calcular_niveles("SHORT", 100.0, 3, 6)
    assert sl == pytest.approx(103.0) and tp == pytest.approx(94.0)


def test_pnl_con_comisiones():
    # LONG 10 unidades de 100 a 106, comisión 0,05% por lado
    pnl = riesgo.calcular_pnl("LONG", 100, 106, 10, 0.05)
    assert pnl == pytest.approx(60 - (1000 + 1060) * 0.0005)  # 58.97
    pnl = riesgo.calcular_pnl("SHORT", 100, 94, 10, 0.05)
    assert pnl == pytest.approx(60 - (1000 + 940) * 0.0005)
    pnl = riesgo.calcular_pnl("SHORT", 100, 103, 10, 0.05)
    assert pnl == pytest.approx(-30 - (1000 + 1030) * 0.0005)
    assert riesgo.calcular_pnl("LONG", 100, 100, 10, 0) == 0


def test_cantidad_con_15_usdt():
    # 15 USDT * 90% * 3x = 40,5 USDT de nocional; a 0,5 => 81 XRP
    assert riesgo.calcular_cantidad(15, 0.9, 3, 0.5) == pytest.approx(81.0)
    assert riesgo.calcular_cantidad(0, 0.9, 3, 0.5) == 0


def test_resultado_tipico_con_15_usdt():
    q = riesgo.calcular_cantidad(15, 0.9, 3, 0.5)
    sl, tp = riesgo.calcular_niveles("LONG", 0.5, 3, 6)
    ganancia = riesgo.calcular_pnl("LONG", 0.5, tp, q, 0.05)
    perdida = riesgo.calcular_pnl("LONG", 0.5, sl, q, 0.05)
    assert ganancia == pytest.approx(2.43 - 0.0412, abs=1e-3)
    assert perdida == pytest.approx(-1.215 - 0.039885, abs=1e-3)


def test_redondeo_y_minimos():
    assert riesgo.redondear_abajo(81.37, 0.1) == pytest.approx(81.3)
    assert riesgo.redondear_abajo(81.37, 1) == 81
    assert riesgo.validar_minimos(81, 0.5, 0.1, 5)[0]
    ok, msg = riesgo.validar_minimos(8, 0.5, 0.1, 5)
    assert not ok and "Nocional" in msg
    ok, msg = riesgo.validar_minimos(0.05, 100, 0.1, 5)
    assert not ok and "Cantidad" in msg
    assert not riesgo.validar_minimos(0, 1, None, None)[0]


def test_tocado_sl_tp():
    assert riesgo.tocado_sl_tp("LONG", 96.9, 97, 106) == "SL"
    assert riesgo.tocado_sl_tp("LONG", 106.1, 97, 106) == "TP"
    assert riesgo.tocado_sl_tp("LONG", 100, 97, 106) is None
    assert riesgo.tocado_sl_tp("SHORT", 103.5, 103, 94) == "SL"
    assert riesgo.tocado_sl_tp("SHORT", 93, 103, 94) == "TP"
    assert riesgo.tocado_sl_tp("SHORT", 100, 103, 94) is None


def test_corte_diario():
    assert riesgo.corte_diario_alcanzado(15, 12, 20)
    assert riesgo.corte_diario_alcanzado(15, 11.9, 20)
    assert not riesgo.corte_diario_alcanzado(15, 12.1, 20)
    assert not riesgo.corte_diario_alcanzado(0, 5, 20)
