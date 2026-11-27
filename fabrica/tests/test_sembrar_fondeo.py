"""La siembra del desafío: copia el equipo entrenado, resetea la cuenta al capital del examen y
arranca plano, pero conserva la experiencia (trades) y los roles (titular/suplente)."""
import json

from fabrica.sembrar_fondeo import sembrar


def _estado_origen():
    return {
        "pausado": True, "apagado": True, "motivo_apagado": "algo", "real_confirmado": True,
        "cuenta": {"equity": 103.47, "pico": 110.0, "dia": "2026-11-24", "inicio_dia": 108.0,
                   "pnl_hoy": -1.2, "racha_hoy": -2, "freno_dia": "x"},
        "cuenta_real": {"equity": 90.0, "auto": ["bot5"], "confirmado": True},
        "bots": {
            "t1": {"id": "t1", "rol": "titular", "simbolo": "BTC/USDT:USDT", "tf": "1h",
                   "estrategia": {}, "trades": [{"r": 1.2}, {"r": 0.5}],
                   "posicion": {"lado": "long", "precio": 60000}, "desde": "2026-10-01T00:00:00"},
            "s1": {"id": "s1", "rol": "suplente", "simbolo": "ETH/USDT:USDT", "tf": "15m",
                   "estrategia": {}, "trades": [], "posicion": None, "desde": "2026-10-01T00:00:00"},
        },
        "eventos": [{"fecha": "2026-11-24", "texto": "viejo"}],
        "creado": "2026-10-01T00:00:00", "testnet_desde": "2026-10-01T00:00:00",
    }


def _sembrar(tmp_path, capital=5000):
    src = tmp_path / "origen.json"
    dst = tmp_path / "fondeo" / "estado_liga.json"
    src.write_text(json.dumps(_estado_origen()), encoding="utf-8")
    sembrar(str(src), str(dst), capital)
    return json.loads(dst.read_text(encoding="utf-8"))


def test_cuenta_se_resetea_al_capital_del_examen(tmp_path):
    e = _sembrar(tmp_path, 5000)
    c = e["cuenta"]
    assert c["equity"] == c["pico"] == c["inicio_dia"] == 5000
    assert c["pnl_hoy"] == 0.0 and c["racha_hoy"] == 0 and c["dia"] == "" and c["freno_dia"] == ""


def test_arranca_plano_sin_posiciones_heredadas(tmp_path):
    e = _sembrar(tmp_path)
    assert all(b["posicion"] is None for b in e["bots"].values())


def test_conserva_equipo_y_experiencia(tmp_path):
    e = _sembrar(tmp_path)
    assert e["bots"]["t1"]["rol"] == "titular" and e["bots"]["s1"]["rol"] == "suplente"
    # la experiencia (trades) se mantiene: es lo que sostiene el estatus de titular
    assert e["bots"]["t1"]["trades"] == [{"r": 1.2}, {"r": 0.5}]


def test_sin_plata_real_de_la_otra_cuenta(tmp_path):
    e = _sembrar(tmp_path)
    assert "cuenta_real" not in e


def test_resetea_fecha_de_inicio_y_banderas(tmp_path):
    e = _sembrar(tmp_path)
    # desde se resetea a hoy (ya no la fecha vieja de la otra cuenta): el desafío empieza ahora
    assert all(not b["desde"].startswith("2026-10-01") for b in e["bots"].values())
    assert e["pausado"] is False and e["apagado"] is False
    assert e["real_confirmado"] is False and e["eventos"] == []


def test_devuelve_resumen_correcto(tmp_path):
    src = tmp_path / "origen.json"
    dst = tmp_path / "estado_liga.json"
    src.write_text(json.dumps(_estado_origen()), encoding="utf-8")
    e = sembrar(str(src), str(dst), 5000)
    b = list(e["bots"].values())
    assert sum(1 for x in b if x["rol"] == "titular") == 1
    assert sum(1 for x in b if x["rol"] == "suplente") == 1
