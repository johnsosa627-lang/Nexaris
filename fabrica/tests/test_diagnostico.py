"""Diagnóstico: detecta señales que no se operaron, con el mismo cálculo que usa el bot en vivo."""
import pandas as pd

from fabrica import diagnostico
from fabrica.config import cargar_config
from tests.conftest import H, T0, escribir_mercados

TENDENCIA = {"lado": "ambos", "reglas": [{"tipo": "ruptura_donchian", "n": 20}],
             "salidas": {"stop_tipo": "atr", "stop": 2.0, "tp_tipo": "atr", "tp": 4.0, "trailing": 0.0, "max_velas": 0}}


def test_senales_sin_operar_y_coincidencia_con_vivo(tmp_path):
    escribir_mercados(str(tmp_path), ["AAA/USDT:USDT"], 0.2, n=3000)
    cfg = cargar_config()
    cfg["datos"]["carpeta"] = str(tmp_path)
    desde = pd.Timestamp(T0 + 2700 * H, unit="ms", tz="UTC").isoformat()
    bot = {"id": "b1", "rol": "titular", "simbolo": "AAA/USDT:USDT", "tf": "1h", "estrategia": TENDENCIA,
           "desde": desde, "trades": [], "posicion": None}
    r = diagnostico.diagnosticar(cfg, [bot, {**bot, "id": "viejo", "rol": "jubilado"}])
    assert len(r) == 1 and r[0]["velas_en_vivo"] == 300
    assert r[0]["senales_vivo"] > 3 and r[0]["senales_vivo"] == r[0]["senales_historia"]  # en vivo calcula igual
    t = diagnostico.texto(r)
    assert "⚠️ b1" in t and "hay algo que revisar" in t
    operando = diagnostico.texto(diagnostico.diagnosticar(cfg, [{**bot, "trades": [{"r": 1}]}]))
    assert "Ninguna señal quedó sin operar" in operando
    sin_datos = diagnostico.diagnosticar(cfg, [{**bot, "simbolo": "ZZZ/USDT:USDT"}])
    assert sin_datos[0]["error"]
