"""Inventa estrategias: al azar + algoritmo genético (las mejores se cruzan y mutan)."""
from __future__ import annotations

import copy
import random

import numpy as np

from . import estrategia as E
from . import metricas as M
from .indicadores import Cache
from .motor import correr


def mutar(e: dict, r: random.Random, max_cond: int) -> dict:
    e = copy.deepcopy(e)
    op = r.random()
    if op < 0.45:  # mover un número un poquito
        if r.random() < 0.4:
            clave = r.choice(["sl_atr", "tp_atr", "max_barras"])
            lo, hi = E.RANGOS[clave]
            v = e[clave] * r.uniform(0.75, 1.3)
            e[clave] = int(min(max(v, lo), hi)) if clave == "max_barras" else round(min(max(v, lo), hi), 2)
        else:
            c = r.choice(e["condiciones"])
            nums = [k for k, v in c.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if nums:
                k = r.choice(nums)
                v = c[k] * r.uniform(0.75, 1.3) if c[k] != 0 else r.uniform(-20, 20)
                c[k] = int(round(v)) if isinstance(c[k], int) else round(v, 2)
                if k in ("n", "n2"):
                    c[k] = max(2, c[k])
                if c.get("n2") is not None and c["n2"] <= c["n"]:
                    c["n2"] = c["n"] + 5
    elif op < 0.7:  # cambiar una condición por otra nueva
        i = r.randrange(len(e["condiciones"]))
        e["condiciones"][i] = E.condicion_al_azar(r)
    elif op < 0.85 and len(e["condiciones"]) < max_cond:
        e["condiciones"].append(E.condicion_al_azar(r))
    elif len(e["condiciones"]) > 1:
        e["condiciones"].pop(r.randrange(len(e["condiciones"])))
    else:
        e["lado"] = "short" if e["lado"] == "long" else "long"
    return e


def cruzar(a: dict, b: dict, r: random.Random, max_cond: int) -> dict:
    hijo = copy.deepcopy(r.choice([a, b]))
    pool = copy.deepcopy(a["condiciones"] + b["condiciones"])
    r.shuffle(pool)
    hijo["condiciones"] = pool[: r.randint(1, min(max_cond, len(pool)))]
    for k in ("sl_atr", "tp_atr", "max_barras"):
        hijo[k] = r.choice([a, b])[k]
    return hijo


def evolucionar(cache: Cache, ini: int, fin: int, cfg: dict, tf: str, semilla: int | None = None,
                costo_rt: float = 0.0012) -> dict:
    """Corre el genético sobre [ini, fin). Devuelve las estrategias evaluadas ordenadas por aptitud,
    cuántas se probaron en total y la varianza de sus Sharpe (para el Deflated Sharpe)."""
    g = cfg["generador"]
    min_ops = cfg["filtros"]["min_operaciones"]
    r = random.Random(semilla)
    vistos: dict[str, tuple] = {}

    def evaluar(e):
        k = E.id_de(e)
        if k not in vistos:
            res = correr(e, cache, ini, fin, costo_rt=costo_rt, funding_8h=cfg["costos"]["funding_8h"], tf=tf)
            m = M.calcular(res.r, res.ts_salida, cfg["riesgo"]["riesgo_por_operacion"])
            vistos[k] = (M.aptitud(m, E.cantidad_parametros(e), min_ops), e, m)
        return vistos[k][0]

    pob = [E.al_azar(r, g["max_condiciones"]) for _ in range(g["poblacion"])]
    for _ in range(g["generaciones"]):
        pob.sort(key=evaluar, reverse=True)
        elite = pob[: max(4, len(pob) // 5)]
        nueva = list(elite)
        while len(nueva) < g["poblacion"]:
            x = r.random()
            if x < 0.15:
                nueva.append(E.al_azar(r, g["max_condiciones"]))  # sangre nueva
            elif x < 0.55:
                nueva.append(cruzar(r.choice(elite), r.choice(elite), r, g["max_condiciones"]))
            else:
                nueva.append(mutar(r.choice(elite), r, g["max_condiciones"]))
        pob = nueva
    for e in pob:
        evaluar(e)
    lista = sorted(vistos.values(), key=lambda t: t[0], reverse=True)
    sharpes = np.array([t[2]["sharpe"] for t in lista if t[2]["operaciones"] > 10])
    return {
        "lista": lista,
        "probadas": len(vistos),
        "var_sharpe": float(np.var(sharpes)) if len(sharpes) > 2 else None,
        "mejor_aptitud": lista[0][0] if lista else -1.0,
    }
