from fabrica import probar_examen as pe


def test_aprueba_al_llegar_a_la_meta():
    dias = [("d1", 0.03), ("d2", 0.03), ("d3", 0.03), ("d4", 0.03)]  # acumula 0.12 >= 0.10
    estado, info = pe.simular(dias, meta_pct=10, dia_pct=4, total_pct=6)
    assert estado == "aprobado" and info["equity"] >= 0.10


def test_rompe_por_limite_diario():
    estado, _ = pe.simular([("d1", -0.05)], meta_pct=10, dia_pct=4, total_pct=6)  # -5% en un día > 4%
    assert estado == "roto_dia"


def test_rompe_por_limite_total_trailing():
    # sube a 0.05 y cae de a poco (cada día < 4%): a los -6% desde el pico rompe el total
    dias = [("d1", 0.05), ("d2", -0.03), ("d3", -0.03)]
    estado, info = pe.simular(dias, meta_pct=10, dia_pct=4, total_pct=6)
    assert estado == "roto_total" and round(info["peor_total"], 4) == 0.06


def test_sin_terminar_si_no_llega_ni_rompe():
    estado, _ = pe.simular([("d1", 0.02), ("d2", 0.02)], meta_pct=10, dia_pct=4, total_pct=6)
    assert estado == "sin_terminar"


def test_rolling_cuenta_cada_arranque():
    dias = [("d1", 0.04), ("d2", 0.04), ("d3", 0.04)]  # desde cualquier día termina sumando bien
    res = pe.simular_rolling(dias, meta_pct=8, dia_pct=4, total_pct=6)
    assert res["arranques"] == 3 and res["pct_aprueba"] > 0 and res["pct_rompe"] == 0


def test_serie_combinada_suma_por_fecha():
    equipo = [{"retornos_diarios": {"2026-01-01": 0.02, "2026-01-02": -0.01}},
              {"retornos_diarios": {"2026-01-01": 0.01}}]
    assert pe.serie_combinada(equipo) == [("2026-01-01", 0.03), ("2026-01-02", -0.01)]


def test_variedad_cubre_monedas_y_tf_distintas():
    reg = [{"simbolo": "A", "tf": "1h"}, {"simbolo": "A", "tf": "1h"}, {"simbolo": "B", "tf": "4h"}]
    equipo = pe._variedad(reg, 2)
    claves = {(r["simbolo"], r["tf"]) for r in equipo}
    assert claves == {("A", "1h"), ("B", "4h")}
