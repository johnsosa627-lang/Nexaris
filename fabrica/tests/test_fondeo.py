from fabrica import fondeo

REGLAS = {"fondeo": {"activo": True, "empresa": "HyroTrader", "fase": "1 paso",
                     "capital": 100, "meta_pct": 10.0, "perdida_dia_pct": 4.0,
                     "perdida_total_pct": 6.0, "trailing": True}}


def test_apagado_devuelve_none():
    assert fondeo.estado({"fondeo": {"activo": False}}, {"equity": 100}) is None
    assert "APAGADO" in fondeo.texto({}, {"equity": 100})


def test_en_camino():
    # ganó 4% (104 de 100), arrancó el día en 102, pico 104
    e = fondeo.estado(REGLAS, {"equity": 104, "pico": 104, "inicio_dia": 102})
    assert e["estado"] == "ok"
    assert round(e["ganancia_pct"], 2) == 4.0 and round(e["falta_meta_pct"], 2) == 6.0
    assert e["margen_dia"] == 4.0                 # límite diario 4 USDT, hoy no perdió desde inicio_dia(102->104)
    assert round(e["margen_total"], 4) == 104 * 0.06  # trailing 6% del pico


def test_aprobado_al_llegar_a_la_meta():
    e = fondeo.estado(REGLAS, {"equity": 110, "pico": 110, "inicio_dia": 108})
    assert e["estado"] == "aprobado"
    assert "alcanzada" in fondeo.texto(REGLAS, {"equity": 110, "pico": 110, "inicio_dia": 108})


def test_roto_por_perdida_diaria():
    # arrancó el día en 103 y cayó a 98: perdió 5 > límite diario 4
    e = fondeo.estado(REGLAS, {"equity": 98, "pico": 105, "inicio_dia": 103})
    assert e["estado"] == "roto" and e["margen_dia"] < 0


def test_roto_por_perdida_total_trailing():
    # pico 110, piso trailing = 110*0.94 = 103.4; equity 103 está por debajo
    e = fondeo.estado(REGLAS, {"equity": 103, "pico": 110, "inicio_dia": 103})
    assert e["estado"] == "roto" and e["margen_total"] < 0


def test_cerca_de_un_limite():
    # perdió 3.2 en el día de un límite de 4 -> queda poco margen (<= 25%)
    e = fondeo.estado(REGLAS, {"equity": 100.8, "pico": 104, "inicio_dia": 104})
    assert e["estado"] in ("cerca", "roto")
