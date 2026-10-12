"""Pruebas de robustez: cada una es un colador. Si una estrategia falla una, se descarta."""
from __future__ import annotations

import copy
import random

import numpy as np

from . import metricas as M
from .indicadores import Cache
from .motor import correr


def out_of_sample(m_is: dict, m_oos: dict, f: dict) -> tuple[bool, str]:
    if m_oos["operaciones"] < f["min_operaciones_oos"]:
        return False, "pocas operaciones en datos nuevos"
    if m_oos["ganancia_pct"] <= 0:
        return False, "pierde en datos que no usó para crearse"
    if m_oos["profit_factor"] < m_is["profit_factor"] * (1 - f["caida_pf_oos_max"]):
        return False, "en datos nuevos el profit factor cae demasiado"
    return True, "ok"


def montecarlo(r: np.ndarray, costo_r: np.ndarray, f: dict, riesgo: float, semilla: int = 0) -> dict:
    """Mezcla el orden, saltea operaciones y encarece costos al azar, miles de veces.
    `costo_r`: lo que costó cada operación en R (para poder duplicarlo)."""
    rng = np.random.default_rng(semilla)
    n = len(r)
    gan, dds, rachas = [], [], []
    for _ in range(f["montecarlo_simulaciones"]):
        orden = rng.permutation(n)
        quedan = orden[rng.random(n) >= f["montecarlo_saltear"]]
        extra = rng.uniform(0, f["montecarlo_costo_extra"])
        rr = r[quedan] - costo_r[quedan] * extra
        eq = M.curva(rr, riesgo)
        gan.append(eq[-1] - 1)
        dds.append(M.max_drawdown(eq))
        rachas.append(M.racha_perdidas(rr))
    return {
        "ganancia_p5": float(np.percentile(gan, 5)),
        "dd_p95": float(np.percentile(dds, 95)),
        "dd_p99": float(np.percentile(dds, 99)),
        "racha_p95": int(np.percentile(rachas, 95)),
        "racha_p99": int(np.percentile(rachas, 99)),
    }


def variantes(e: dict, cuantas: int, semilla: int = 0, rango: float = 0.15) -> list[dict]:
    """Copias de la estrategia con cada número movido ±15 %."""
    r = random.Random(semilla)
    out = []
    for _ in range(cuantas):
        v = copy.deepcopy(e)
        for k in ("sl_atr", "tp_atr"):
            v[k] = round(v[k] * r.uniform(1 - rango, 1 + rango), 2)
        v["max_barras"] = max(2, int(round(v["max_barras"] * r.uniform(1 - rango, 1 + rango))))
        for c in v["condiciones"]:
            for k, val in list(c.items()):
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    continue
                nv = val * r.uniform(1 - rango, 1 + rango) if val != 0 else r.uniform(-10, 10)
                c[k] = max(2, int(round(nv))) if isinstance(val, int) and k in ("n", "n2") else (
                    int(round(nv)) if isinstance(val, int) else round(nv, 2))
            if c.get("n2") is not None and c["n2"] <= c["n"]:
                c["n2"] = c["n"] + 2
        out.append(v)
    return out


def sensibilidad(e: dict, cache: Cache, ini: int, fin: int, f: dict, **kw) -> tuple[bool, float]:
    vs = variantes(e, f["perturbacion_variantes"])
    ok = 0
    for v in vs:
        res = correr(v, cache, ini, fin, **kw)
        m = M.calcular(res.r)
        if m["operaciones"] >= 20 and m["ganancia_pct"] > 0 and m["profit_factor"] > 1.05:
            ok += 1
    frac = ok / len(vs)
    return frac >= f["perturbacion_frac_ok"], frac


def con_retraso(e: dict, cache: Cache, ini: int, fin: int, **kw) -> tuple[bool, dict]:
    res = correr(e, cache, ini, fin, retraso=1, **kw)
    m = M.calcular(res.r)
    return (m["ganancia_pct"] > 0 and m["profit_factor"] > 1.0), m


def multimercado(e: dict, otros: list[tuple[Cache, int, int]], f: dict, **kw) -> tuple[bool, float]:
    if not otros:
        return True, 1.0
    ok = 0
    for cache, ini, fin in otros:
        res = correr(e, cache, ini, fin, **kw)
        m = M.calcular(res.r)
        if m["operaciones"] >= 20 and m["ganancia_pct"] > 0:
            ok += 1
    frac = ok / len(otros)
    return frac >= f["multimercado_frac_ok"], frac


def puntaje_robustez(m_is: dict, m_oos: dict, mc: dict, frac_sens: float, frac_multi: float) -> float:
    """0 a 100: qué tan confiable parece (no cuánto gana)."""
    p = 0.0
    p += 25 * min(1.0, m_oos["profit_factor"] / max(m_is["profit_factor"], 1e-9))
    p += 25 * frac_sens
    p += 20 * frac_multi
    p += 15 * max(0.0, min(1.0, 1 - mc["dd_p95"] / 0.3))
    p += 15 * max(0.0, min(1.0, m_is["estabilidad"]))
    return round(p, 1)
