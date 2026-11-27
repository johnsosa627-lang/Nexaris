"""Modo examen de fondeo en la Liga en vivo: el capital de arranque es el del desafío y el /estado
lo muestra como DESAFÍO DE FONDEO (no como 'práctica / Demo de Binance')."""
from fabrica.config import cargar_config
from fabrica.liga import Liga

from tests.test_vivo import MercadoFalso


def cfg_fondeo(activo=True, capital=5000, capital_inicial=100):
    cfg = cargar_config()
    cfg["riesgo"]["capital_inicial"] = capital_inicial
    cfg.setdefault("fondeo", {}).update({"activo": activo, "empresa": "HyroTrader", "fase": "1 paso",
                                         "capital": capital, "meta_pct": 10.0, "perdida_dia_pct": 4.0,
                                         "perdida_total_pct": 6.0, "trailing": True, "riesgo_pct": 0.3})
    return cfg


def _liga(tmp_path, cfg, modo="testnet"):
    return Liga(cfg, str(tmp_path), MercadoFalso(), None, lambda m: None,
                reloj=lambda: 1_700_000_000.0, modo=modo)


def test_capital_de_arranque_es_el_del_examen(tmp_path):
    liga = _liga(tmp_path, cfg_fondeo(activo=True, capital=5000, capital_inicial=100))
    c = liga.e["cuenta"]
    # arranca en 5000 (el del desafío), no en capital_inicial (100)
    assert c["equity"] == c["pico"] == c["inicio_dia"] == 5000


def test_sin_examen_usa_capital_inicial(tmp_path):
    liga = _liga(tmp_path, cfg_fondeo(activo=False, capital=5000, capital_inicial=100))
    assert liga.e["cuenta"]["equity"] == 100


def test_estado_muestra_desafio_de_fondeo(tmp_path):
    liga = _liga(tmp_path, cfg_fondeo(activo=True, capital=5000))
    txt = liga.texto_estado()
    assert "DESAFÍO DE FONDEO" in txt and "HyroTrader" in txt and "5000" in txt
    assert "Demo de Binance" not in txt


def test_estado_sin_examen_no_dice_desafio(tmp_path):
    liga = _liga(tmp_path, cfg_fondeo(activo=False, capital_inicial=100))
    txt = liga.texto_estado()
    assert "DESAFÍO DE FONDEO" not in txt
