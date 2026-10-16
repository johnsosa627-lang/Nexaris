"""Chequeo de salud: detecta solo los problemas que antes había que descubrir a mano."""
import json
import os

from fabrica import salud
from fabrica.config import cargar_config
from tests.conftest import H, T0, escribir_mercados

DIA = 86_400_000


def _cfg(tmp_path, n):
    escribir_mercados(str(tmp_path / "datos"), ["AAA/USDT:USDT"], 0.0, n=n)
    cfg = cargar_config()
    cfg["datos"].update(carpeta=str(tmp_path / "datos"), simbolos=["AAA/USDT:USDT"], temporalidades=["1h", "4h"],
                        desde="2021-01-01")
    cfg["salida"]["carpeta"] = str(tmp_path / "res")
    return cfg


def _ciclo(cfg, nombre, inventadas):
    carpeta = os.path.join(cfg["salida"]["carpeta"], nombre)
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, "embudo.json"), "w") as f:
        json.dump({"embudo": {"inventadas": inventadas}}, f)
    with open(os.path.join(cfg["salida"]["carpeta"], "ultimo_ciclo.txt"), "w") as f:
        f.write(nombre)


def test_detecta_historia_cortada_como_la_de_1000_velas(tmp_path):
    cfg = _cfg(tmp_path, 1000)                      # ~42 días de velas de 1 hora
    fin = T0 + 1000 * H
    r = salud.chequeo(cfg, fin + H, prendida_desde_ms=fin)
    assert any("muy corta" in p for p in r["problemas"])
    assert "problema" in salud.texto(r)


def test_datos_completos_y_ciclo_que_inventa_estan_en_orden(tmp_path):
    cfg = _cfg(tmp_path, 9500)                      # ~13 meses
    fin = T0 + 9500 * H
    _ciclo(cfg, "ciclo_20220130_030000", 4200)    # la serie termina el 31/01/2022
    r = salud.chequeo(cfg, fin + H, prendida_desde_ms=fin)
    assert r["problemas"] == [], r["problemas"]
    assert any("4200" in o for o in r["ok"]) and "todo en orden" in salud.texto(r)


def test_detecta_ciclo_vacio_ciclo_atrasado_y_datos_viejos(tmp_path):
    cfg = _cfg(tmp_path, 9500)
    fin = T0 + 9500 * H
    _ciclo(cfg, "ciclo_20210101_030000", 0)
    r = salud.chequeo(cfg, fin + 5 * DIA, prendida_desde_ms=fin)
    textos = " ".join(r["problemas"])
    assert "no inventó ninguna" in textos and "no corre un ciclo" in textos and "viejos" in textos
    # con un ciclo en marcha no se alarma por eso
    r2 = salud.chequeo(cfg, fin + 5 * DIA, ciclo_en_curso=True, prendida_desde_ms=fin)
    assert not any("ciclo" in p for p in r2["problemas"])


def test_sin_datos_y_sin_ciclo(tmp_path):
    cfg = _cfg(tmp_path, 10)
    cfg["datos"]["simbolos"] = ["ZZZ/USDT:USDT"]
    r = salud.chequeo(cfg, T0 + 3 * DIA, prendida_desde_ms=T0)
    textos = " ".join(r["problemas"])
    assert "no hay datos" in textos and "nunca terminó un ciclo" in textos


def test_bots_sin_velas_o_sin_operar_cuando_deberian():
    import pandas as pd
    ahora = int(pd.Timestamp("2026-10-20 12:00", tz="UTC").timestamp() * 1000)
    diarios = {f"2023-01-{d:02d}": 0.01 for d in range(1, 31)}   # backtest: 300 operaciones en 29 días ≈ 10 por día
    base = {"rol": "titular", "simbolo": "XRP/USDT:USDT", "tf": "15m", "desde": "2026-10-18T12:00:00+00:00",
            "r_backtest": [0.5] * 300, "retornos_diarios": diarios, "trades": [], "posicion": None}
    al_dia = {**base, "id": "b1", "ultima_vela_ts": ahora - 20 * 60_000}
    sin_velas = {**base, "id": "b2", "ultima_vela_ts": ahora - 10 * 3_600_000}
    nunca = {**base, "id": "b3", "ultima_vela_ts": 0}
    lento = {**base, "id": "b4", "ultima_vela_ts": ahora - 20 * 60_000, "r_backtest": [0.5] * 3}  # ~1 cada 10 días
    p, ok = salud.revisar_bots([al_dia, sin_velas, nunca, lento, {**base, "id": "j", "rol": "jubilado"}], ahora)
    textos = " ".join(p)
    assert "b1" in textos and "ya debería haber operado" in textos          # 2 días sin operar con ~10 por día
    assert "b2" in textos and "no recibe velas" in textos
    assert "b3" in textos and "ninguna vela" in textos
    assert "b4" not in textos and "j " not in textos                         # opera poco: todavía es normal
    assert ok == ["2 de 4 bots reciben velas al día"]
    operando = {**al_dia, "trades": [{"r": 1.0}]}
    assert salud.revisar_bots([operando], ahora)[0] == []
