"""Examen final: cada estrategia aprobada se prueba UNA SOLA VEZ en los meses guardados.

Si aprueba, entra al "banco" (de ahí salen los suplentes de la liga en la etapa 5).
Si reprueba, queda descartada para siempre: no se reajusta con esos datos ni se vuelve a examinar.

    python -m fabrica.examen                    # examina las aprobadas del último ciclo
    python -m fabrica.examen --ciclo ciclo_20261012_101500
"""
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import numpy as np

from .config import cargar_config
from .datos import alinear_funding, cargar_funding, cargar_velas
from .generador import Evaluador
from .motor import Costos

log = logging.getLogger("fabrica")


def _leer_json(ruta, defecto):
    if not os.path.exists(ruta):
        return defecto
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _escribir_json(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    temporal = ruta + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    os.replace(temporal, ruta)


def ruta_registro(cfg):
    return os.path.join(cfg["salida"]["carpeta"], "examenes.json")


def carpeta_banco(cfg):
    return os.path.join(cfg["salida"]["carpeta"], "banco")


def ya_examinadas(cfg) -> dict:
    return _leer_json(ruta_registro(cfg), {})


def examinar(cfg: dict, registro: dict) -> dict:
    """Corre el examen de UNA estrategia. Si ya se examinó antes, devuelve el resultado guardado sin recalcular."""
    examenes = ya_examinadas(cfg)
    if registro["id"] in examenes:
        return {**examenes[registro["id"]], "ya_examinada": True}

    e = dict(cfg["examen"])
    if registro.get("nivel") == "exploracion":
        e.update((cfg.get("exploracion") or {}).get("examen", {}))
    carpeta = cfg["datos"]["carpeta"]
    velas = cargar_velas(carpeta, registro["simbolo"], registro["tf"])
    corte = int(registro["corte_examen_ms"])
    inicio = int(np.searchsorted(velas["ts"].to_numpy(), corte, side="left"))
    fund = alinear_funding(velas["ts"].to_numpy(), cargar_funding(carpeta, registro["simbolo"]), registro["tf"])
    r = cfg["riesgo"]
    ev = Evaluador(velas, fund, Costos.desde_config(cfg), r["riesgo_por_operacion_pct"], r["apalancamiento_max"])
    # Las señales usan la historia previa para "calentar" los indicadores; las operaciones empiezan en el corte
    res = ev.correr(registro["estrategia"], desde=inicio)
    m = res.metricas
    caida_prevista = (registro.get("montecarlo") or {}).get("drawdown_p95_pct") or cfg["filtros"]["max_drawdown_pct"]
    motivos = []
    if m["operaciones"] < e["min_operaciones"]:
        motivos.append(f"pocas operaciones ({m['operaciones']} < {e['min_operaciones']})")
    if m["retorno_pct"] <= 0:
        motivos.append(f"perdió plata ({m['retorno_pct']:+.1f}%)")
    if m["profit_factor"] < e["min_profit_factor"]:
        motivos.append(f"profit factor bajo ({m['profit_factor']:.2f} < {e['min_profit_factor']})")
    if m["max_drawdown_pct"] > caida_prevista:
        motivos.append(f"cayó más de lo previsto ({m['max_drawdown_pct']:.1f}% > {caida_prevista:.1f}%)")
    resultado = {
        "id": registro["id"], "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ciclo": registro.get("ciclo"), "simbolo": registro["simbolo"], "tf": registro["tf"],
        "aprobada": not motivos, "motivos": motivos, "velas_examen": len(velas) - inicio,
        "desde_ms": corte, "hasta_ms": int(velas["ts"].iloc[-1]) if len(velas) else corte,
        "metricas": {k: v for k, v in m.items() if k != "anios"},
        "caida_prevista_pct": caida_prevista,
    }
    examenes[registro["id"]] = resultado
    _escribir_json(ruta_registro(cfg), examenes)

    if resultado["aprobada"]:
        trabajo = ev.correr(registro["estrategia"], hasta=inicio)
        _escribir_json(os.path.join(carpeta_banco(cfg), f"{registro['id']}.json"), {
            **registro, "examen": resultado, "estado": "banco",
            "fecha_ingreso": resultado["fecha"],
            # Lo que "promete" el backtest: se usa en vivo para detectar si se aleja de lo esperado
            "retornos_backtest": [round(float(x), 6) for x in trabajo.operaciones["retorno"]],
            "r_backtest": [round(float(x), 4) for x in trabajo.operaciones["r"]],
            # Resultado por día: sirve para medir cuánto se parecen dos estrategias (correlación)
            "retornos_diarios": retornos_diarios(trabajo.operaciones),
        })
    log.info("Examen %s (%s %s): %s %s", registro["id"], registro["simbolo"], registro["tf"],
             "APROBADA" if resultado["aprobada"] else "REPROBADA", "; ".join(motivos))
    return resultado


def retornos_diarios(ops) -> dict:
    if len(ops) == 0:
        return {}
    import pandas as pd
    dias = pd.to_datetime(ops["salida_ts"], unit="ms", utc=True).dt.strftime("%Y-%m-%d")
    return {d: round(float(v), 6) for d, v in ops["retorno"].groupby(dias.values).sum().items()}


def examinar_ciclo(cfg: dict, carpeta_ciclo: str) -> list:
    carpeta = os.path.join(carpeta_ciclo, "aprobadas")
    resultados = []
    if not os.path.isdir(carpeta):
        return resultados
    for nombre in sorted(os.listdir(carpeta)):
        if not nombre.endswith(".json"):
            continue
        ruta = os.path.join(carpeta, nombre)
        registro = _leer_json(ruta, None)
        resultado = examinar(cfg, registro)
        if not resultado.get("ya_examinada"):
            registro["examen"] = resultado
            _escribir_json(ruta, registro)
        resultados.append(resultado)
    return resultados


def banco(cfg) -> list:
    carpeta = carpeta_banco(cfg)
    if not os.path.isdir(carpeta):
        return []
    return [_leer_json(os.path.join(carpeta, n), None) for n in sorted(os.listdir(carpeta)) if n.endswith(".json")]


def ultimo_ciclo(cfg) -> str:
    ruta = os.path.join(cfg["salida"]["carpeta"], "ultimo_ciclo.txt")
    if not os.path.exists(ruta):
        raise SystemExit("Todavía no se corrió ningún ciclo: python -m fabrica.ciclo")
    with open(ruta, encoding="utf-8") as f:
        return os.path.join(cfg["salida"]["carpeta"], f.read().strip())


def main():
    from .informes import informe_ciclo
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    p = argparse.ArgumentParser(description="Examen final de las estrategias aprobadas")
    p.add_argument("--ciclo", help="nombre de la carpeta del ciclo (por defecto, el último)")
    args = p.parse_args()
    cfg = cargar_config()
    carpeta = os.path.join(cfg["salida"]["carpeta"], args.ciclo) if args.ciclo else ultimo_ciclo(cfg)
    examinar_ciclo(cfg, carpeta)
    print(informe_ciclo(cfg, carpeta))


if __name__ == "__main__":
    main()
