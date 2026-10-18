import json
import os

import pytest

from fabrica import datos
from fabrica.config import cargar_config
from fabrica.examen import banco, examinar, ya_examinadas
from fabrica.informes import tarjeta
from tests.conftest import serie_con_cambio

TENDENCIA = {"lado": "ambos", "reglas": [{"tipo": "ruptura_donchian", "n": 20}],
             "salidas": {"stop_tipo": "atr", "stop": 2.0, "tp_tipo": "ninguno", "tp": 0.0, "trailing": 3.0, "max_velas": 0}}
N = 16000


def preparar(tmp_path, phi_examen, semilla=4):
    cfg = cargar_config()
    cfg["datos"]["carpeta"] = str(tmp_path / "datos")
    cfg["salida"]["carpeta"] = str(tmp_path / "res")
    v = serie_con_cambio(N, 0, 0.25, 0.25, semilla)
    _, examen, corte = datos.dividir_examen(v, 6)
    v = serie_con_cambio(N, N - len(examen), 0.25, phi_examen, semilla)
    ruta = datos.ruta_velas(cfg["datos"]["carpeta"], "AAA/USDT:USDT", "1h")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    v.to_csv(ruta, index=False, compression="gzip")
    registro = {"id": "prueba0001", "simbolo": "AAA/USDT:USDT", "tf": "1h", "estrategia": TENDENCIA,
                "explicacion": "Compra cuando el precio supera el máximo de las últimas 20 velas.",
                "corte_examen_ms": corte, "montecarlo": {"drawdown_p95_pct": 30.0, "pct_ganadoras": 100,
                                                         "simulaciones": 1000},
                "metricas_trabajo": {"operaciones": 600, "ganadoras_pct": 40, "retorno_pct": 120,
                                     "profit_factor": 1.6, "max_drawdown_pct": 15, "racha_perdedora": 9},
                "ciclo": "ciclo_prueba"}
    return cfg, registro, corte


def test_aprueba_si_el_mercado_sigue_igual_y_entra_al_banco(tmp_path):
    cfg, registro, corte = preparar(tmp_path, 0.25)
    r = examinar(cfg, registro)
    assert r["aprobada"], r["motivos"]
    assert r["desde_ms"] == corte and r["metricas"]["operaciones"] >= 10
    b = banco(cfg)
    assert len(b) == 1 and b[0]["id"] == "prueba0001" and b[0]["estado"] == "banco"
    assert len(b[0]["retornos_backtest"]) > 100 and b[0]["examen"]["aprobada"]


def test_reprueba_si_el_mercado_cambia(tmp_path):
    cfg, registro, _ = preparar(tmp_path, -0.4)  # en los meses guardados el precio va y viene: la tendencia no sirve
    r = examinar(cfg, registro)
    assert not r["aprobada"] and r["motivos"]
    assert banco(cfg) == []


def test_reprueba_si_cae_mas_de_lo_previsto(tmp_path):
    cfg, registro, _ = preparar(tmp_path, 0.25)
    registro["montecarlo"]["drawdown_p95_pct"] = 0.5
    r = examinar(cfg, registro)
    assert not r["aprobada"] and any("cayó más" in m for m in r["motivos"])


def test_se_examina_una_sola_vez(tmp_path):
    cfg, registro, _ = preparar(tmp_path, -0.4)
    primero = examinar(cfg, registro)
    # aunque cambien los datos (o alguien quiera "volver a intentar"), el resultado no se recalcula
    preparar(tmp_path, 0.25)
    segundo = examinar(cfg, registro)
    assert segundo["ya_examinada"] and segundo["aprobada"] == primero["aprobada"] is False
    assert segundo["metricas"] == primero["metricas"]
    assert list(ya_examinadas(cfg)) == ["prueba0001"]


def test_tarjeta_en_lenguaje_simple(tmp_path):
    cfg, registro, _ = preparar(tmp_path, 0.25)
    assert "pendiente" in tarjeta(registro)
    registro["examen"] = examinar(cfg, registro)
    t = tarjeta(registro)
    assert "AAA, velas de 1 hora" in t and "Qué hace:" in t and "15 dólares" in t
    assert "9 veces seguidas" in t and "APROBÓ" in t


def _al_banco(tmp_path, phi_nuevo, hasta_frac=0.8):
    """Banco con una estrategia cuyo examen terminó en `hasta_frac`; después el mercado sigue con `phi_nuevo`."""
    cfg = cargar_config()
    cfg["datos"]["carpeta"] = str(tmp_path / "datos")
    cfg["salida"]["carpeta"] = str(tmp_path / "res")
    corte = int(N * hasta_frac)
    v = serie_con_cambio(N, corte, 0.25, phi_nuevo, 4)
    ruta = datos.ruta_velas(cfg["datos"]["carpeta"], "AAA/USDT:USDT", "1h")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    v.to_csv(ruta, index=False, compression="gzip")
    os.makedirs(os.path.join(cfg["salida"]["carpeta"], "banco"))
    reg = {"id": "banco0001", "simbolo": "AAA/USDT:USDT", "tf": "1h", "estrategia": TENDENCIA, "estado": "banco",
           "examen": {"aprobada": True, "hasta_ms": int(v["ts"].iloc[corte - 1])}}
    with open(os.path.join(cfg["salida"]["carpeta"], "banco", "banco0001.json"), "w", encoding="utf-8") as f:
        json.dump(reg, f)
    return cfg


def test_revision_con_datos_nuevos_vence_la_que_deja_de_funcionar(tmp_path):
    from fabrica.examen import revisar_banco
    cfg = _al_banco(tmp_path, -0.4)  # después del examen el mercado va y viene: la tendencia deja de servir
    r = revisar_banco(cfg, str(tmp_path))
    assert r["revisadas"] == 1 and [v["id"] for v in r["vencidas"]] == ["banco0001"]
    assert banco(cfg) == []  # ya no entra a la liga
    guardada = banco(cfg, todas=True)[0]
    assert guardada["estado"] == "vencida" and guardada["seguimiento"]["operaciones"] >= 10
    assert os.path.exists(tmp_path / "seguimiento.json")


def test_revision_con_datos_nuevos_mantiene_la_que_sigue_bien(tmp_path):
    from fabrica.examen import revisar_banco
    cfg = _al_banco(tmp_path, 0.25)
    r = revisar_banco(cfg)
    assert r["revisadas"] == 1 and r["vencidas"] == []
    b = banco(cfg)
    assert len(b) == 1 and b[0]["seguimiento"]["retorno_pct"] > 0


def test_revision_sin_velas_nuevas_no_toca_nada(tmp_path):
    from fabrica.examen import revisar_banco
    cfg = _al_banco(tmp_path, -0.4, hasta_frac=1.0)
    r = revisar_banco(cfg)
    assert r == {"revisadas": 0, "sin_datos_nuevos": 1, "vencidas": []}
    assert banco(cfg)[0]["estado"] == "banco" and "seguimiento" not in banco(cfg)[0]
