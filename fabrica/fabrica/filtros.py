"""Los 7 filtros (el "colador"). Una estrategia avanza solo si pasa el filtro anterior."""
import math
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Callable, Optional

import numpy as np
import pandas as pd

from .estrategia import perturbar
from .generador import Evaluador, fitness

NORMAL = NormalDist()
EULER = 0.5772156649


# ------------------------------------------------------------------ herramientas
def precios_al_azar(velas: pd.DataFrame, rng: np.random.Generator, funding: Optional[np.ndarray] = None):
    """Mezcla al azar el orden de las velas: misma volatilidad y forma de velas, pero sin ningún patrón real."""
    v = velas.reset_index(drop=True)
    pc = v["close"].shift(1).to_numpy()
    rel = {k: (v[k].to_numpy() / pc) for k in ("open", "high", "low", "close")}
    orden = np.concatenate([[0], 1 + rng.permutation(len(v) - 1)])
    cierre = np.empty(len(v))
    cierre[0] = v["close"].iloc[0]
    cierre[1:] = cierre[0] * np.cumprod(rel["close"][orden[1:]])
    previo = np.concatenate([[np.nan], cierre[:-1]])
    nuevo = v.copy()
    for k in ("open", "high", "low"):
        nuevo.loc[1:, k] = (previo * rel[k][orden])[1:]
    nuevo["close"] = cierre
    nuevo["volume"] = v["volume"].to_numpy()[orden]
    fund = None if funding is None else np.asarray(funding)[orden]
    return nuevo, fund


def montecarlo(ops: pd.DataFrame, comision_pct: float, simulaciones: int = 1000, saltear_pct: float = 10,
               multiplicador_comision: float = 2.0, rng: Optional[np.random.Generator] = None) -> dict:
    """Mezcla el orden de las operaciones, saltea algunas al azar y cobra comisión extra."""
    rng = rng or np.random.default_rng(0)
    ret = ops["retorno"].to_numpy(dtype=float)
    pe, ps = ops["precio_entrada"].to_numpy(), ops["precio_salida"].to_numpy()
    extra = ops["apalancamiento"].to_numpy() * (multiplicador_comision - 1) * comision_pct / 100 * (pe + ps) / pe
    ret = ret - extra
    finales, caidas = np.empty(simulaciones), np.empty(simulaciones)
    for s in range(simulaciones):
        r = ret[rng.permutation(len(ret))]
        r = r[rng.random(len(r)) >= saltear_pct / 100]
        curva = np.concatenate([[1.0], np.cumprod(1 + r)])
        pico = np.maximum.accumulate(curva)
        finales[s] = curva[-1]
        caidas[s] = ((pico - curva) / pico).max() * 100
    return {
        "simulaciones": simulaciones,
        "pct_ganadoras": float((finales > 1).mean() * 100),
        "retorno_p5_pct": float((np.percentile(finales, 5) - 1) * 100),
        "retorno_mediana_pct": float((np.median(finales) - 1) * 100),
        "drawdown_p95_pct": float(np.percentile(caidas, 95)),
        "drawdown_max_pct": float(caidas.max()),
    }


def deflated_sharpe(sr: float, n_obs: int, asimetria: float, curtosis: float, n_ensayos: int, var_sr: float) -> float:
    """Probabilidad de que el Sharpe sea real y no fruto de haber probado muchas estrategias
    (Bailey y López de Prado, 2014). SR por operación, sin anualizar."""
    if n_obs < 3:
        return 0.0
    if n_ensayos > 1 and var_sr > 0:
        sr0 = math.sqrt(var_sr) * ((1 - EULER) * NORMAL.inv_cdf(1 - 1 / n_ensayos)
                                   + EULER * NORMAL.inv_cdf(1 - 1 / (n_ensayos * math.e)))
    else:
        sr0 = 0.0
    denominador = math.sqrt(max(1 - asimetria * sr + (curtosis - 1) / 4 * sr ** 2, 1e-6))
    return float(NORMAL.cdf((sr - sr0) * math.sqrt(n_obs - 1) / denominador))


# ------------------------------------------------------------------ contexto de una moneda/temporalidad
@dataclass
class Combo:
    simbolo: str
    tf: str
    ev: Evaluador                       # todo el período de trabajo (sin el examen final)
    corte_is: int                       # índice donde termina la parte usada para crear (in-sample)
    otros: Callable[[], list]           # [(nombre, Evaluador)] otras monedas, misma temporalidad
    vecinos: Callable[[], list]         # [(nombre, Evaluador)] misma moneda, temporalidad vecina
    suerte: Callable[[], dict]          # resultado del generador sobre precios al azar
    n_ensayos: int
    var_sr: float
    cfg: dict = field(default_factory=dict)


def _ok(cond, **detalle):
    return bool(cond), detalle


# ------------------------------------------------------------------ los filtros
def f1_metricas(c, combo, f, rng):
    res = combo.ev.correr(c["estrategia"])
    m = res.metricas
    c["_ops"], c["metricas_trabajo"] = res.operaciones, m
    return _ok(m["operaciones"] >= f["min_operaciones"] and m["profit_factor"] > f["min_profit_factor"]
               and m["ret_dd"] > f["min_ret_dd"] and m["max_drawdown_pct"] < f["max_drawdown_pct"]
               and m["estabilidad"] > f["min_estabilidad"] and m["anios_positivos_pct"] > f["min_pct_anios_positivos"],
               operaciones=m["operaciones"], profit_factor=round(m["profit_factor"], 2), ret_dd=round(m["ret_dd"], 2),
               drawdown=round(m["max_drawdown_pct"], 2), estabilidad=round(m["estabilidad"], 2),
               anios_positivos=round(m["anios_positivos_pct"], 1))


def f2_fuera_de_muestra(c, combo, f, rng):
    est, ev = c["estrategia"], combo.ev
    m = ev.correr(est, desde=combo.corte_is).metricas
    c["metricas_oos"] = m
    if not (m["retorno_pct"] > 0 and m["profit_factor"] >= f["oos_min_profit_factor"]):
        return _ok(False, oos_retorno=round(m["retorno_pct"], 2), oos_profit_factor=round(m["profit_factor"], 2))
    # Walk-forward: en cada ventana se elige la mejor variante con el pasado y se prueba en la ventana siguiente
    variantes = [est] + [perturbar(rng, est, int(rng.integers(1, 3))) for _ in range(f["wf_variantes"])]
    sens = [ev.senales(v) for v in variantes]
    n = len(ev.velas)
    bordes = np.linspace(0, n, f["wf_ventanas"] + 1).astype(int)
    min_ops = f["min_operaciones"]
    positivas, rets = 0, []
    for j in range(1, f["wf_ventanas"]):
        fit = [fitness(ev.correr(v, hasta=bordes[j], sen=s).metricas, v, int(min_ops * bordes[j] / n))
               for v, s in zip(variantes, sens)]
        k = int(np.argmax(fit))
        prueba = ev.correr(variantes[k], desde=bordes[j], hasta=bordes[j + 1], sen=sens[k])
        positivas += prueba.metricas["retorno_pct"] > 0
        rets.extend(prueba.operaciones["retorno"].tolist())
    r = np.array(rets)
    pf = r[r > 0].sum() / -r[r < 0].sum() if (r < 0).any() else (999.0 if len(r) else 0.0)
    pct = positivas / (f["wf_ventanas"] - 1) * 100
    c["walk_forward"] = {"ventanas_positivas_pct": pct, "profit_factor": float(pf), "operaciones": len(r)}
    return _ok(pct >= f["wf_min_pct_ventanas_positivas"] and pf >= f["wf_min_profit_factor"],
               oos_retorno=round(m["retorno_pct"], 2), oos_profit_factor=round(m["profit_factor"], 2),
               wf_ventanas_positivas_pct=round(pct, 1), wf_profit_factor=round(float(pf), 2))


def f3_montecarlo(c, combo, f, rng):
    mc = montecarlo(c["_ops"], combo.ev.costos.comision_pct, f["montecarlo_simulaciones"],
                    f["montecarlo_saltear_pct"], f["montecarlo_multiplicador_comision"], rng)
    c["montecarlo"] = mc
    return _ok(mc["pct_ganadoras"] >= f["montecarlo_confianza_pct"]
               and mc["drawdown_p95_pct"] <= f.get("montecarlo_max_drawdown_p95_pct", 25.0),
               **{k: round(v, 2) for k, v in mc.items()})


def f4_sobreajuste(c, combo, f, rng):
    base = c["metricas_trabajo"]["ret_dd"]
    resultados = [combo.ev.correr(perturbar(rng, c["estrategia"], int(rng.integers(1, 3)))).metricas
                  for _ in range(f["robustez_variantes"])]
    rentables = np.mean([m["profit_factor"] > 1 and m["retorno_pct"] > 0 for m in resultados]) * 100
    mediana = float(np.median([m["ret_dd"] for m in resultados]))
    c["robustez"] = {"pct_rentables": float(rentables), "ret_dd_mediana": mediana, "ret_dd_original": base}
    return _ok(rentables >= f["robustez_min_pct_rentables"] and mediana >= f["robustez_min_ret_dd_relativo"] * base,
               pct_variantes_rentables=round(float(rentables), 1), ret_dd_mediana=round(mediana, 2),
               ret_dd_original=round(base, 2))


def _rentable(m):
    return m["operaciones"] >= 20 and m["profit_factor"] > 1 and m["retorno_pct"] > 0


def f5_otros_mercados(c, combo, f, rng):
    otros = {nombre: _rentable(ev.correr(c["estrategia"]).metricas) for nombre, ev in combo.otros()}
    vecinos = {nombre: _rentable(ev.correr(c["estrategia"]).metricas) for nombre, ev in combo.vecinos()}
    c["otros_mercados"] = {"monedas": otros, "temporalidades": vecinos}
    pct = (np.mean(list(otros.values())) * 100) if otros else 0.0
    return _ok(otros and pct >= f["otras_monedas_min_pct"] and sum(vecinos.values()) >= f["temporalidad_vecina_min"],
               monedas_rentables=f"{sum(otros.values())}/{len(otros)}",
               temporalidades_rentables=f"{sum(vecinos.values())}/{len(vecinos)}")


def f6_entrada_tarde(c, combo, f, rng):
    m = combo.ev.correr(c["estrategia"], retraso=1).metricas
    c["entrada_tarde"] = {"profit_factor": m["profit_factor"], "retorno_pct": m["retorno_pct"]}
    return _ok(m["retorno_pct"] > 0 and m["profit_factor"] >= f["retraso_min_profit_factor"],
               profit_factor=round(m["profit_factor"], 2), retorno=round(m["retorno_pct"], 2))


def f7_antisuerte(c, combo, f, rng):
    suerte = combo.suerte()
    umbral = max(suerte["fitness_max"], 0.0) * f["antisuerte_margen"]
    m = c["metricas"]
    dsr = deflated_sharpe(m["sharpe_operacion"], m["operaciones"], m["asimetria"], m["curtosis"],
                          combo.n_ensayos, combo.var_sr)
    c["antisuerte"] = {"fitness": c["fitness"], "fitness_suerte": suerte["fitness_max"], "dsr": dsr}
    return _ok(c["fitness"] > umbral and dsr >= f["dsr_min"],
               fitness=round(c["fitness"], 2), mejor_de_la_suerte=round(suerte["fitness_max"], 2),
               deflated_sharpe=round(dsr, 3))


FILTROS = [
    ("1_metricas", "métricas mínimas", f1_metricas),
    ("2_fuera_de_muestra", "datos no usados + walk-forward", f2_fuera_de_muestra),
    ("3_montecarlo", "Monte Carlo", f3_montecarlo),
    ("4_sobreajuste", "mover un poco los números", f4_sobreajuste),
    ("5_otros_mercados", "otras monedas y temporalidad vecina", f5_otros_mercados),
    ("6_entrada_tarde", "entrar una vela tarde", f6_entrada_tarde),
    ("7_antisuerte", "anti-suerte + Deflated Sharpe", f7_antisuerte),
]


def aplicar_filtros(candidata: dict, combo: Combo, cfg_filtros: dict, rng) -> list:
    """Devuelve [(clave, aprobado, detalle)] hasta el primer filtro que no pasa."""
    pasos = []
    for clave, _, funcion in FILTROS:
        ok, detalle = funcion(candidata, combo, cfg_filtros, rng)
        pasos.append((clave, ok, detalle))
        if not ok:
            break
    return pasos
