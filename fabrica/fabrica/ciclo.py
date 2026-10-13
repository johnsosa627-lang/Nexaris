"""Un ciclo completo de la fábrica: inventar -> colar -> guardar las aprobadas.

    python -m fabrica.ciclo                 # ciclo completo con config.yaml
    python -m fabrica.ciclo --rapido        # versión chica para probar que todo anda
    python -m fabrica.ciclo --simbolos XRP/USDT:USDT --tfs 1h
"""
import argparse
import copy
import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

import numpy as np

from .config import cargar_config
from .datos import alinear_funding, cargar_funding, cargar_velas, dividir_examen
from .estrategia import describir
from .filtros import FILTROS, Combo, aplicar_filtros, precios_al_azar
from .generador import Evaluador, evolucionar, mejores
from .motor import Costos

log = logging.getLogger("fabrica")

VECINAS = {"15m": ["1h"], "1h": ["15m", "4h"], "4h": ["1h"]}
MIN_VELAS = 1000


class Mercado:
    """Carga (una sola vez) los datos de trabajo de cada moneda/temporalidad. Nunca entrega el examen final."""

    def __init__(self, cfg):
        self.cfg = cfg
        self._cache = {}

    def trabajo(self, simbolo, tf):
        clave = (simbolo, tf)
        if clave not in self._cache:
            carpeta = self.cfg["datos"]["carpeta"]
            velas = cargar_velas(carpeta, simbolo, tf)
            trabajo, _, corte = dividir_examen(velas, self.cfg["datos"]["meses_examen"])
            fund = alinear_funding(trabajo["ts"].to_numpy(), cargar_funding(carpeta, simbolo), tf) if len(trabajo) else None
            self._cache[clave] = (trabajo, fund, corte)
        return self._cache[clave]

    def evaluador(self, simbolo, tf):
        trabajo, fund, _ = self.trabajo(simbolo, tf)
        if len(trabajo) < MIN_VELAS:
            return None
        r = self.cfg["riesgo"]
        return Evaluador(trabajo, fund, Costos.desde_config(self.cfg), r["riesgo_por_operacion_pct"], r["apalancamiento_max"])


def _parametros_generador(g, min_ops):
    return dict(poblacion=g["poblacion"], generaciones=g["generaciones"], elite_pct=g["elite_pct"],
                prob_cruce=g["prob_cruce"], prob_mutacion=g["prob_mutacion"], max_filtros=g["max_filtros"],
                min_operaciones=min_ops)


def procesar_combo(cfg: dict, simbolo: str, tf: str, semilla: int) -> dict:
    """Inventa estrategias para una moneda/temporalidad y las pasa por el colador."""
    inicio = time.time()
    rng = np.random.default_rng(semilla)
    g, f = cfg["generador"], cfg["filtros"]
    mercado = Mercado(cfg)
    trabajo, fund, corte_examen = mercado.trabajo(simbolo, tf)
    resultado = {"simbolo": simbolo, "tf": tf, "embudo": {}, "aprobadas": [], "descartes": []}
    if len(trabajo) < MIN_VELAS:
        resultado["error"] = f"pocos datos ({len(trabajo)} velas)"
        return resultado

    n_is = int(len(trabajo) * g["fraccion_creacion"])
    costos = Costos.desde_config(cfg)
    r = cfg["riesgo"]
    ev_is = Evaluador(trabajo.iloc[:n_is], None if fund is None else fund[:n_is], costos,
                      r["riesgo_por_operacion_pct"], r["apalancamiento_max"])
    min_ops_is = max(20, int(f["min_operaciones"] * g["fraccion_creacion"]))
    archivo = evolucionar(ev_is, rng, **_parametros_generador(g, min_ops_is))
    # Las que ya rindieron examen en ciclos anteriores no se vuelven a evaluar (el examen es UNA sola vez)
    examinadas = set(cfg.get("_examinadas", []))
    previas = [c for c in mejores(archivo, len(archivo)) if c["fitness"] > 0 and _id(c) in examinadas]
    candidatas = [copy.deepcopy(c) for c in mejores(archivo, len(archivo))
                  if c["fitness"] > 0 and _id(c) not in examinadas][: g["candidatas"]]

    # Varianza del Sharpe que daría el puro azar (ninguna estrategia con ventaja real): ~1/operaciones
    ops_por_ensayo = [a["metricas"]["operaciones"] for a in archivo.values() if a["metricas"].get("operaciones", 0) >= 30]
    var_sr_azar = float(np.median([1.0 / n for n in ops_por_ensayo])) if ops_por_ensayo else 0.0
    suerte_cache = {}

    def suerte():
        if not suerte_cache:
            mejores_fit, rng_s = [], np.random.default_rng(semilla + 1)
            for _ in range(f["antisuerte_repeticiones"]):
                velas_azar, fund_azar = precios_al_azar(trabajo.iloc[:n_is], rng_s, None if fund is None else fund[:n_is])
                ev_azar = Evaluador(velas_azar, fund_azar, costos, r["riesgo_por_operacion_pct"], r["apalancamiento_max"])
                arch = evolucionar(ev_azar, rng_s, **_parametros_generador(g, min_ops_is))
                mejores_fit.append(max(a["fitness"] for a in arch.values()))
            suerte_cache.update(fitness_max=float(max(mejores_fit)), repeticiones=len(mejores_fit))
        return suerte_cache

    def otros():
        return [(s, e) for s in cfg["datos"]["simbolos"] if s != simbolo
                for e in [mercado.evaluador(s, tf)] if e is not None]

    def vecinos():
        return [(t, e) for t in VECINAS.get(tf, []) if t in cfg["datos"]["temporalidades"]
                for e in [mercado.evaluador(simbolo, t)] if e is not None]

    combo = Combo(simbolo, tf, Evaluador(trabajo, fund, costos, r["riesgo_por_operacion_pct"], r["apalancamiento_max"]),
                  n_is, otros, vecinos, suerte, len(archivo), var_sr_azar)

    embudo = {"inventadas": len(archivo), "ya_examinadas_antes": len(previas), "candidatas": len(candidatas)}
    embudo.update({clave: 0 for clave, _, _ in FILTROS})
    embudo["aprobadas_exploracion"] = 0
    exploracion = cfg.get("exploracion") or {}
    for cand in candidatas:
        pasos = aplicar_filtros(cand, combo, f, rng)
        for clave, ok, _ in pasos:
            embudo[clave] += ok
        if len(pasos) == len(FILTROS) and pasos[-1][1]:
            resultado["aprobadas"].append(_registro(cand, simbolo, tf, corte_examen, pasos))
            continue
        clave, _, detalle = pasos[-1]
        resultado["descartes"].append({"id": _id(cand), "filtro": clave, "detalle": detalle})
        # Modo exploración: con filtros más flojos, SOLO para practicar (nunca opera con plata real)
        if exploracion.get("activa"):
            cand_x = copy.deepcopy(cand)
            pasos_x = aplicar_filtros(cand_x, combo, {**f, **exploracion["filtros"]}, rng)
            if len(pasos_x) == len(FILTROS) and pasos_x[-1][1]:
                embudo["aprobadas_exploracion"] += 1
                resultado["aprobadas"].append(_registro(cand_x, simbolo, tf, corte_examen, pasos_x, "exploracion"))
    resultado["embudo"] = embudo
    resultado["suerte"] = suerte_cache or None
    resultado["segundos"] = round(time.time() - inicio, 1)
    log.info("%s %s: %d inventadas, %d aprobadas (%.0fs)", simbolo, tf, len(archivo),
             len(resultado["aprobadas"]), resultado["segundos"])
    return resultado


def _id(cand):
    from .estrategia import identificador
    return identificador(cand["estrategia"])


def _limpiar(x):
    """Convierte tipos de numpy a tipos JSON."""
    if isinstance(x, dict):
        return {str(k): _limpiar(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, (list, tuple)):
        return [_limpiar(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def _registro(cand, simbolo, tf, corte_examen, pasos, nivel="estricto"):
    est = cand["estrategia"]
    return _limpiar({
        "id": _id(cand), "simbolo": simbolo, "tf": tf, "nivel": nivel, "explicacion": describir(est), "estrategia": est,
        "fitness": cand["fitness"], "metricas_creacion": cand["metricas"],
        "metricas_trabajo": cand.get("metricas_trabajo"), "metricas_fuera_de_muestra": cand.get("metricas_oos"),
        "walk_forward": cand.get("walk_forward"), "montecarlo": cand.get("montecarlo"),
        "robustez": cand.get("robustez"), "otros_mercados": cand.get("otros_mercados"),
        "entrada_tarde": cand.get("entrada_tarde"), "antisuerte": cand.get("antisuerte"),
        "filtros": {clave: detalle for clave, _, detalle in pasos},
        "corte_examen_ms": corte_examen, "examen": None,  # el examen final se hace en la etapa 4
    })


def _trabajo(args):
    cfg, simbolo, tf, semilla = args
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    return procesar_combo(cfg, simbolo, tf, semilla)


def ciclo(cfg: dict, simbolos=None, tfs=None, procesos=None) -> dict:
    simbolos = simbolos or cfg["datos"]["simbolos"]
    tfs = tfs or cfg["datos"]["temporalidades"]
    semilla = cfg["generador"].get("semilla")
    semilla = int(semilla) if semilla not in (None, "") else int(time.time())
    tareas = [(cfg, s, t, semilla + i * 1000) for i, (s, t) in enumerate((s, t) for s in simbolos for t in tfs)]
    procesos = procesos if procesos is not None else cfg["generador"].get("procesos", 0)
    procesos = procesos or os.cpu_count() or 1
    inicio = datetime.now(timezone.utc)
    from .examen import examinar_ciclo, ya_examinadas
    cfg = {**cfg, "_examinadas": sorted(ya_examinadas(cfg))}
    tareas = [(cfg, s, t, sem) for _, s, t, sem in tareas]
    if procesos > 1 and len(tareas) > 1:
        with ProcessPoolExecutor(max_workers=min(procesos, len(tareas))) as pool:
            resultados = list(pool.map(_trabajo, tareas))
    else:
        resultados = [procesar_combo(*t) for t in tareas]
    resumen = guardar_ciclo(cfg, resultados, inicio, semilla)
    if cfg.get("examen", {}).get("automatico", True):
        from .informes import informe_ciclo
        resumen["examenes"] = examinar_ciclo(cfg, resumen["carpeta"])
        resumen["informe"] = informe_ciclo(cfg, resumen["carpeta"])
    return resumen


def guardar_ciclo(cfg, resultados, inicio, semilla) -> dict:
    nombre = inicio.strftime("ciclo_%Y%m%d_%H%M%S")
    carpeta = os.path.join(cfg["salida"]["carpeta"], nombre)
    os.makedirs(os.path.join(carpeta, "aprobadas"), exist_ok=True)
    embudo = {"inventadas": 0, "ya_examinadas_antes": 0, "candidatas": 0, **{clave: 0 for clave, _, _ in FILTROS},
              "aprobadas_exploracion": 0}
    aprobadas = []
    for r in resultados:
        for k, v in r.get("embudo", {}).items():
            embudo[k] = embudo.get(k, 0) + v
        for a in r["aprobadas"]:
            a["ciclo"] = nombre
            aprobadas.append(a)
            with open(os.path.join(carpeta, "aprobadas", f"{a['id']}.json"), "w", encoding="utf-8") as fh:
                json.dump(a, fh, indent=2, ensure_ascii=False)
    resumen = _limpiar({
        "ciclo": nombre, "inicio": inicio.isoformat(timespec="seconds"),
        "fin": datetime.now(timezone.utc).isoformat(timespec="seconds"), "semilla": semilla,
        "embudo": embudo, "aprobadas": [a["id"] for a in aprobadas],
        "por_mercado": [{k: r.get(k) for k in ("simbolo", "tf", "embudo", "suerte", "segundos", "error")} for r in resultados],
        "descartes": {f"{r['simbolo']} {r['tf']}": r["descartes"] for r in resultados},
    })
    with open(os.path.join(carpeta, "embudo.json"), "w", encoding="utf-8") as fh:
        json.dump(resumen, fh, indent=2, ensure_ascii=False)
    texto = resumen_simple(resumen, aprobadas)
    with open(os.path.join(carpeta, "resumen.txt"), "w", encoding="utf-8") as fh:
        fh.write(texto)
    with open(os.path.join(cfg["salida"]["carpeta"], "ultimo_ciclo.txt"), "w", encoding="utf-8") as fh:
        fh.write(nombre)
    resumen["carpeta"] = carpeta
    resumen["texto"] = texto
    return resumen


def resumen_simple(resumen: dict, aprobadas: list) -> str:
    e = resumen["embudo"]
    lineas = [f"Ciclo {resumen['ciclo']}",
              f"Se inventaron y probaron {e['inventadas']} estrategias. Las {e['candidatas']} mejores pasaron al colador:"]
    for clave, nombre, _ in FILTROS:
        lineas.append(f"  {clave[0]}. {nombre:<40} pasaron {e[clave]}")
    if aprobadas:
        lineas.append(f"\n{len(aprobadas)} estrategia(s) aprobada(s). Falta el examen final (etapa 4):")
        for a in aprobadas:
            m = a["metricas_trabajo"]
            lineas.append(f"\n- {a['id']} ({a['simbolo']} {a['tf']}): {a['explicacion']}\n"
                          f"  {m['operaciones']} operaciones, profit factor {m['profit_factor']:.2f}, "
                          f"peor caída {m['max_drawdown_pct']:.1f}%, Monte Carlo gana en el "
                          f"{a['montecarlo']['pct_ganadoras']:.0f}% de los casos.")
    else:
        lineas.append("\nNinguna estrategia pasó todos los filtros en este ciclo. Es normal: el colador es exigente\n"
                      "a propósito, para no arriesgar plata en estrategias que ganaron por suerte.")
    return "\n".join(lineas)


MODO_RAPIDO = {"generador": {"poblacion": 40, "generaciones": 5, "candidatas": 10},
               "filtros": {"montecarlo_simulaciones": 200, "robustez_variantes": 10, "wf_variantes": 4,
                           "antisuerte_repeticiones": 1}}


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    p = argparse.ArgumentParser(description="Ciclo de la fábrica de estrategias")
    p.add_argument("--simbolos", nargs="*")
    p.add_argument("--tfs", nargs="*")
    p.add_argument("--procesos", type=int)
    p.add_argument("--rapido", action="store_true", help="presupuesto chico, para probar")
    args = p.parse_args()
    cfg = cargar_config()
    if args.rapido:
        for seccion, valores in MODO_RAPIDO.items():
            cfg[seccion].update(valores)
    resumen = ciclo(cfg, args.simbolos, args.tfs, args.procesos)
    print("\n" + resumen.get("informe", resumen["texto"]))
    print(f"\nResultados guardados en {resumen['carpeta']}")


if __name__ == "__main__":
    main()
