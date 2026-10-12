"""Un ciclo completo de la fábrica: inventar → filtrar → examen final → candidatos para la liga."""
from __future__ import annotations

import json
import logging
import time
from collections import Counter

import numpy as np
import pandas as pd

from . import datos as D
from . import estrategia as E
from . import metricas as M
from . import robustez as R
from .config import DATA_DIR, costo_ida_vuelta
from .datos import TF_MS
from .generador import evolucionar
from .indicadores import Cache
from .motor import correr

log = logging.getLogger(__name__)

EXAMINADOS = DATA_DIR / "examinados.json"


def _leer_examinados() -> set:
    try:
        return set(json.loads(EXAMINADOS.read_text()))
    except Exception:
        return set()


def _guardar_examinados(s: set) -> None:
    EXAMINADOS.parent.mkdir(parents=True, exist_ok=True)
    EXAMINADOS.write_text(json.dumps(sorted(s)))


def cortes(df: pd.DataFrame, tf: str, dias_examen: int, frac_is: float = 0.7) -> tuple[int, int, int]:
    """Devuelve (fin_creacion, fin_oos, n). El examen final va de fin_oos al final."""
    n = len(df)
    examen = int(dias_examen * 86_400_000 / TF_MS[tf])
    fin_oos = max(int(n * 0.5), n - examen)
    fin_is = int(fin_oos * frac_is)
    return fin_is, fin_oos, n


def linea_base_suerte(df: pd.DataFrame, tf: str, fin_is: int, cfg: dict, semilla: int) -> float:
    """Corre la misma fábrica sobre precios barajados (sin ningún patrón real).
    Lo mejor que salga de ahí es lo que da la pura suerte."""
    mejor = -1.0
    for k in range(cfg["filtros"]["anti_suerte_rondas"]):
        falso = D.barajar(df.iloc[:fin_is].reset_index(drop=True), semilla + 1000 + k, tf)
        res = evolucionar(Cache(falso), 0, len(falso), cfg, tf, semilla=semilla + 2000 + k,
                          costo_rt=costo_ida_vuelta(cfg))
        mejor = max(mejor, res["mejor_aptitud"])
    return mejor


def correr_ciclo(cfg: dict, conjuntos: dict[tuple[str, str], pd.DataFrame] | None = None,
                 avisar=lambda txt: None) -> dict:
    """`conjuntos`: {(simbolo, tf): velas}. Si no se pasa, se leen los datos guardados."""
    t0 = time.time()
    f = cfg["filtros"]
    riesgo = cfg["riesgo"]["riesgo_por_operacion"]
    costo_rt = costo_ida_vuelta(cfg)
    kw = {"costo_rt": costo_rt, "funding_8h": cfg["costos"]["funding_8h"]}
    semilla = cfg["generador"].get("semilla") or int(time.time()) % 100_000
    if conjuntos is None:
        conjuntos = {}
        for s in cfg["datos"]["simbolos"]:
            for tf in cfg["datos"]["temporalidades"]:
                df = D.cargar(s, tf)
                if df is not None and len(df) > 2000:
                    conjuntos[(s, tf)] = df
    caches = {k: Cache(v) for k, v in conjuntos.items()}
    info_cortes = {k: cortes(v, k[1], cfg["datos"]["dias_examen_final"]) for k, v in conjuntos.items()}
    examinados = _leer_examinados()
    embudo: Counter = Counter()
    motivos: Counter = Counter()
    ganadoras = []

    for (sim, tf), df in conjuntos.items():
        cache = caches[(sim, tf)]
        fin_is, fin_oos, n = info_cortes[(sim, tf)]
        avisar(f"🏭 Fábrica trabajando en {sim.split(':')[0]} {tf}…")
        gen = evolucionar(cache, 0, fin_is, cfg, tf, semilla=semilla, costo_rt=costo_rt)
        embudo["inventadas"] += gen["probadas"]
        base = linea_base_suerte(df, tf, fin_is, cfg, semilla)
        otros = [(caches[k], 0, info_cortes[k][1]) for k in conjuntos if k[1] == tf and k[0] != sim]
        for apt, e, m_is in gen["lista"][:60]:
            e = dict(e, simbolo=sim, tf=tf)
            ok, mot = M.pasa_filtros(m_is, f)
            if not ok:
                motivos[mot] += 1
                continue
            embudo["pasan_metricas"] += 1
            res_oos = correr(e, cache, fin_is, fin_oos, tf=tf, **kw)
            m_oos = M.calcular(res_oos.r, res_oos.ts_salida, riesgo)
            ok, mot = R.out_of_sample(m_is, m_oos, f)
            if not ok:
                motivos[mot] += 1
                continue
            embudo["pasan_datos_nuevos"] += 1
            if apt <= base:
                motivos["no supera a la pura suerte"] += 1
                continue
            res_is = correr(e, cache, 0, fin_is, tf=tf, **kw)
            # Varianza teórica 1/T: las pruebas del genético son muy parecidas entre sí (no independientes),
            # así que usar la varianza entre ellas exageraría la corrección. La línea base de arriba ya
            # mide la suerte del genético directamente.
            dsr = M.deflated_sharpe(m_is["sharpe"], m_is["operaciones"], gen["probadas"])
            if dsr < f["deflated_sharpe_min"]:
                motivos["Sharpe explicable por suerte (deflated)"] += 1
                continue
            embudo["pasan_anti_suerte"] += 1
            todo_r = np.r_[res_is.r, res_oos.r]
            todo_c = np.r_[res_is.costo_r, res_oos.costo_r]
            mc = R.montecarlo(todo_r, todo_c, f, riesgo, semilla)
            if mc["ganancia_p5"] <= 0 or mc["dd_p95"] > f["max_drawdown"] * 1.5:
                motivos["falla Monte Carlo"] += 1
                continue
            embudo["pasan_montecarlo"] += 1
            ok_s, frac_s = R.sensibilidad(e, cache, 0, fin_oos, f, tf=tf, **kw)
            if not ok_s:
                motivos["se rompe al mover un número (sobreajuste)"] += 1
                continue
            ok_d, _ = R.con_retraso(e, cache, 0, fin_oos, tf=tf, **kw)
            if not ok_d:
                motivos["no aguanta entrar una vela tarde"] += 1
                continue
            ok_m, frac_m = R.multimercado(e, otros, f, tf=tf, **kw)
            if not ok_m:
                motivos["no funciona en otras monedas"] += 1
                continue
            embudo["pasan_robustez"] += 1
            eid = E.id_de(e)
            if eid in examinados:
                continue
            examinados.add(eid)
            res_ex = correr(e, cache, fin_oos, n, tf=tf, **kw)
            m_ex = M.calcular(res_ex.r, res_ex.ts_salida, riesgo)
            if m_ex["operaciones"] < 5 or m_ex["ganancia_pct"] <= 0 or m_ex["profit_factor"] < 1.0:
                motivos["reprobó el examen final"] += 1
                continue
            embudo["aprueban_examen_final"] += 1
            ganadoras.append({
                "id": eid, "estrategia": e, "explicacion": E.explicar(e),
                "puntaje": R.puntaje_robustez(m_is, m_oos, mc, frac_s, frac_m),
                "metricas_creacion": m_is, "metricas_datos_nuevos": m_oos, "metricas_examen": m_ex,
                "montecarlo": mc, "linea_base_suerte": round(base, 3), "aptitud": round(apt, 3),
                "deflated_sharpe": round(dsr, 3), "creada": int(time.time() * 1000),
            })
    _guardar_examinados(examinados)
    ganadoras.sort(key=lambda g: g["puntaje"], reverse=True)
    informe = {"fecha": int(time.time() * 1000), "minutos": round((time.time() - t0) / 60, 1),
               "embudo": dict(embudo), "motivos": dict(motivos.most_common(8)), "ganadoras": ganadoras}
    d = DATA_DIR / "ciclos"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"ciclo_{informe['fecha']}.json").write_text(json.dumps(informe, indent=1, default=str))
    return informe


def texto_embudo(inf: dict) -> str:
    e = inf["embudo"]
    lineas = [
        f"🏭 Ciclo terminado en {inf['minutos']} min",
        f"Inventadas: {e.get('inventadas', 0)}",
        f"Pasan métricas: {e.get('pasan_metricas', 0)}",
        f"Pasan datos nuevos: {e.get('pasan_datos_nuevos', 0)}",
        f"Pasan anti-suerte: {e.get('pasan_anti_suerte', 0)}",
        f"Pasan Monte Carlo: {e.get('pasan_montecarlo', 0)}",
        f"Pasan robustez: {e.get('pasan_robustez', 0)}",
        f"✅ Aprueban examen final: {e.get('aprueban_examen_final', 0)}",
    ]
    if not inf["ganadoras"]:
        lineas.append("Esta vez ninguna estrategia fue confiable. Es normal: el sistema te cuida de "
                      "estrategias que solo ganaron de casualidad. La semana que viene prueba de nuevo.")
    return "\n".join(lineas)
