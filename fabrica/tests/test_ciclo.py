import json
import os

import pytest

from fabrica.ciclo import MODO_RAPIDO, ciclo
from fabrica.config import cargar_config
from fabrica.filtros import FILTROS
from tests.conftest import escribir_mercados

SIMBOLOS = ["AAA/USDT:USDT", "BBB/USDT:USDT", "CCC/USDT:USDT"]


def _cfg(tmp_path, phi):
    escribir_mercados(str(tmp_path / "datos"), SIMBOLOS, phi, n=16000)
    cfg = cargar_config()
    cfg["datos"].update(carpeta=str(tmp_path / "datos"), simbolos=SIMBOLOS, temporalidades=["1h", "4h"], meses_examen=3)
    cfg["salida"]["carpeta"] = str(tmp_path / "res")
    cfg["generador"]["semilla"] = 1
    for seccion, valores in MODO_RAPIDO.items():
        cfg[seccion].update(valores)
    return cfg


def test_ciclo_con_tendencias_reales_aprueba_y_guarda(tmp_path):
    cfg = _cfg(tmp_path, 0.2)
    cfg["exploracion"]["activa"] = False
    r = ciclo(cfg, simbolos=SIMBOLOS[:1], tfs=["1h"], procesos=1)
    e = r["embudo"]
    pasos = ["candidatas"] + [f[0] for f in FILTROS]
    assert all(e[a] >= e[b] for a, b in zip(pasos, pasos[1:])), e
    assert e["inventadas"] > 100 and len(r["aprobadas"]) >= 1
    carpeta = r["carpeta"]
    assert os.path.exists(os.path.join(carpeta, "embudo.json")) and os.path.exists(os.path.join(carpeta, "resumen.txt"))
    with open(os.path.join(carpeta, "aprobadas", r["aprobadas"][0] + ".json"), encoding="utf-8") as f:
        a = json.load(f)
    assert a["explicacion"] and a["examen"]["id"] == a["id"] and a["corte_examen_ms"]
    assert a["montecarlo"]["drawdown_p95_pct"] > 0 and a["antisuerte"]["dsr"] >= 0.95
    assert "aprobada" in r["texto"]
    # examen final automático + informe
    assert len(r["examenes"]) == len(r["aprobadas"])
    assert "INFORME DE LA FÁBRICA" in r["informe"] and "Examen final" in r["informe"]
    assert os.path.exists(os.path.join(carpeta, "informe.txt"))
    # un segundo ciclo igual no vuelve a examinar las mismas estrategias
    r2 = ciclo(cfg, simbolos=SIMBOLOS[:1], tfs=["1h"], procesos=1)
    assert r2["embudo"]["ya_examinadas_antes"] >= len(r["aprobadas"])
    assert not set(r2["aprobadas"]) & set(r["aprobadas"])


def test_ciclo_con_precios_al_azar_no_aprueba_nada(tmp_path):
    cfg = _cfg(tmp_path, 0.0)
    cfg["exploracion"]["activa"] = False
    r = ciclo(cfg, simbolos=SIMBOLOS[:1], tfs=["1h"], procesos=1)
    assert r["aprobadas"] == [] and r["embudo"]["inventadas"] > 100
    assert "Ninguna estrategia" in r["texto"]


def test_ciclo_en_paralelo_y_mercado_sin_datos(tmp_path):
    cfg = _cfg(tmp_path, 0.0)
    cfg["datos"]["simbolos"] = SIMBOLOS + ["ZZZ/USDT:USDT"]
    r = ciclo(cfg, simbolos=["AAA/USDT:USDT", "ZZZ/USDT:USDT"], tfs=["4h"], procesos=2)
    errores = {m["simbolo"]: m["error"] for m in r["por_mercado"]}
    assert errores["ZZZ/USDT:USDT"].startswith("pocos datos") and errores["AAA/USDT:USDT"] is None


def test_exploracion_aprueba_con_filtros_flojos_y_las_marca(tmp_path):
    import glob
    cfg = _cfg(tmp_path, 0.12)  # ventaja moderada: no pasa lo estricto, sí lo flojo
    # La búsqueda del modo rápido es corta y depende de la semilla: se prueban algunas hasta que encuentre
    for semilla in (1, 2, 3, 4, 5):
        cfg["generador"]["semilla"] = semilla
        flojo = ciclo(cfg, simbolos=SIMBOLOS[:1], tfs=["1h"], procesos=1)
        if flojo["embudo"]["aprobadas_exploracion"]:
            break
    assert flojo["embudo"]["7_antisuerte"] == 0 and flojo["embudo"]["aprobadas_exploracion"] >= 1
    assert "filtros flojos" in flojo["informe"]
    registros = [json.load(open(p, encoding="utf-8")) for p in glob.glob(os.path.join(flojo["carpeta"], "aprobadas", "*.json"))]
    assert registros and all(r["nivel"] == "exploracion" for r in registros)
    assert all(r["montecarlo"] and r["antisuerte"] for r in registros)


def test_las_ganadoras_en_vivo_entran_como_semillas(tmp_path):
    import json as _json
    from fabrica.ciclo import ganadoras_en_vivo
    est = {"lado": "long", "reglas": [{"tipo": "ruptura_donchian", "n": 20}],
           "salidas": {"stop_tipo": "atr", "stop": 2.0, "tp_tipo": "ninguno", "tp": 0.0, "trailing": 3.0, "max_velas": 0}}
    tr = lambda r: {"r": r}
    bots = {"gana": {"id": "gana", "rol": "suplente", "simbolo": "XRP/USDT:USDT", "tf": "1h", "estrategia": est,
                     "trades": [tr(1.0)] * 3 + [tr(-1.0)] * 2},
            "pierde": {"id": "pierde", "rol": "titular", "simbolo": "SOL/USDT:USDT", "tf": "1h", "estrategia": est,
                       "trades": [tr(-1.0)] * 5},
            "pocas": {"id": "pocas", "rol": "suplente", "simbolo": "ADA/USDT:USDT", "tf": "1h", "estrategia": est,
                      "trades": [tr(3.0)] * 2},
            "jubilado": {"id": "jubilado", "rol": "jubilado", "simbolo": "BNB/USDT:USDT", "tf": "1h", "estrategia": est,
                         "trades": [tr(2.0)] * 9}}
    (tmp_path / "estado_liga.json").write_text(_json.dumps({"bots": bots}))
    semillas = ganadoras_en_vivo(str(tmp_path))
    assert len(semillas) == 1 and "gana" in semillas[0]["famosa"] and semillas[0]["reglas"] == est["reglas"]
    assert ganadoras_en_vivo(str(tmp_path / "no_existe")) == []


def test_si_una_moneda_falla_el_ciclo_sigue(tmp_path, monkeypatch):
    from fabrica import ciclo as C
    cfg = _cfg(tmp_path, 0.0)
    original = C.procesar_combo

    def roto(cfg_, simbolo, tf, semilla):
        if simbolo == "BBB/USDT:USDT":
            raise MemoryError("sin memoria")
        return original(cfg_, simbolo, tf, semilla)
    monkeypatch.setattr(C, "procesar_combo", roto)
    r = C.ciclo(cfg, simbolos=["AAA/USDT:USDT", "BBB/USDT:USDT"], tfs=["4h"], procesos=1)
    errores = {m["simbolo"]: m["error"] for m in r["por_mercado"]}
    assert errores["BBB/USDT:USDT"].startswith("MemoryError") and errores["AAA/USDT:USDT"] is None
    assert r["embudo"]["inventadas"] > 0
