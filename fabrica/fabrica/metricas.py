"""Métricas estilo StrategyQuant, calculadas sobre la lista de operaciones (en R)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def curva(r: np.ndarray, riesgo: float = 0.01) -> np.ndarray:
    """Capital (empezando en 1) después de cada operación, arriesgando `riesgo` cada vez."""
    return np.cumprod(1 + riesgo * np.asarray(r)) if len(r) else np.array([1.0])


def max_drawdown(eq: np.ndarray) -> float:
    eq = np.r_[1.0, eq]
    pico = np.maximum.accumulate(eq)
    return float(np.max(1 - eq / pico))


def racha_perdidas(r: np.ndarray) -> int:
    m = k = 0
    for v in r:
        k = k + 1 if v <= 0 else 0
        m = max(m, k)
    return m


def estabilidad(eq: np.ndarray) -> float:
    """R² de la curva de capital (en log) contra una recta: 1 = sube parejito."""
    if len(eq) < 3:
        return 0.0
    y = np.log(eq)
    x = np.arange(len(y))
    if np.std(y) == 0:
        return 0.0
    rr = np.corrcoef(x, y)[0, 1] ** 2
    pendiente = np.polyfit(x, y, 1)[0]
    return float(rr if pendiente > 0 else -rr)


def calcular(r: np.ndarray, ts_salida: np.ndarray | None = None, riesgo: float = 0.01) -> dict:
    r = np.asarray(r, dtype=float)
    n = len(r)
    if n == 0:
        return {"operaciones": 0, "ganancia_pct": 0.0, "profit_factor": 0.0, "max_dd": 0.0, "ret_dd": 0.0,
                "win_rate": 0.0, "payoff": 0.0, "expectancy_r": 0.0, "sqn": 0.0, "sharpe": 0.0,
                "sortino": 0.0, "estabilidad": 0.0, "racha_perdidas": 0, "frac_anios_ganadores": 0.0,
                "por_anio": {}}
    eq = curva(r, riesgo)
    gan = r[r > 0].sum()
    per = -r[r <= 0].sum()
    pf = float(gan / per) if per > 0 else float("inf") if gan > 0 else 0.0
    dd = max_drawdown(eq)
    neto = float(eq[-1] - 1)
    sd = float(np.std(r, ddof=1)) if n > 1 else 0.0
    sd_neg = float(np.std(np.minimum(r, 0), ddof=1)) if n > 1 else 0.0
    m = float(r.mean())
    wins, losses = r[r > 0], r[r <= 0]
    por_anio = {}
    frac = 0.0
    if ts_salida is not None and len(ts_salida) == n:
        anios = pd.to_datetime(ts_salida, unit="ms").year
        s = pd.Series(r).groupby(np.asarray(anios)).sum()
        por_anio = {int(k): round(float(v), 2) for k, v in s.items()}
        frac = float((s > 0).mean())
    return {
        "operaciones": n,
        "ganancia_pct": round(100 * neto, 2),
        "profit_factor": round(min(pf, 99.0), 3),
        "max_dd": round(dd, 4),
        "ret_dd": round(neto / dd, 2) if dd > 0 else 99.0,
        "win_rate": round(float(len(wins) / n), 3),
        "payoff": round(float(wins.mean() / -losses.mean()), 2) if len(wins) and len(losses) and losses.mean() < 0 else 0.0,
        "expectancy_r": round(m, 4),
        "sqn": round(math.sqrt(min(n, 100)) * m / sd, 2) if sd > 0 else 0.0,
        "sharpe": round(m / sd, 4) if sd > 0 else 0.0,
        "sortino": round(m / sd_neg, 4) if sd_neg > 0 else 0.0,
        "estabilidad": round(estabilidad(eq), 3),
        "racha_perdidas": racha_perdidas(r),
        "frac_anios_ganadores": round(frac, 2),
        "por_anio": por_anio,
    }


def pasa_filtros(m: dict, f: dict) -> tuple[bool, str]:
    reglas = [
        (m["operaciones"] >= f["min_operaciones"], "pocas operaciones"),
        (m["profit_factor"] >= f["profit_factor"], "profit factor bajo"),
        (m["ret_dd"] >= f["ret_dd"], "ganancia/caída baja"),
        (m["max_dd"] <= f["max_drawdown"], "caída máxima muy grande"),
        (m["estabilidad"] >= f["estabilidad"], "curva poco pareja"),
        (m["sqn"] >= f["sqn"], "SQN bajo"),
        (m["frac_anios_ganadores"] >= f["frac_anios_ganadores"], "pierde en muchos años"),
    ]
    for ok, motivo in reglas:
        if not ok:
            return False, motivo
    return True, "ok"


def aptitud(m: dict, n_param: int, min_ops: int) -> float:
    """Puntaje para el algoritmo genético: premia ganar parejo con poca caída y castiga complicación."""
    if m["operaciones"] < max(20, min_ops // 4) or m["expectancy_r"] <= 0:
        return -1.0 + m["expectancy_r"]
    falta = min(1.0, m["operaciones"] / min_ops)
    base = m["sqn"] * max(m["estabilidad"], 0) * min(m["profit_factor"], 3) / 3
    return base * falta * (1 - 0.03 * max(0, n_param - 5))


def deflated_sharpe(sharpe: float, n_obs: int, n_pruebas: int, asim: float = 0.0, curt: float = 3.0,
                    var_sharpes: float | None = None) -> float:
    """Probabilidad de que el Sharpe sea real y no suerte, corrigiendo por cuántas estrategias se probaron
    (López de Prado, 2014). Sharpe por operación."""
    from statistics import NormalDist

    nd = NormalDist()
    if n_obs < 3 or n_pruebas < 1:
        return 0.0
    v = var_sharpes if var_sharpes is not None else 1.0 / n_obs
    g = 0.5772156649
    n = max(n_pruebas, 2)
    sr0 = math.sqrt(v) * ((1 - g) * nd.inv_cdf(1 - 1 / n) + g * nd.inv_cdf(1 - 1 / (n * math.e)))
    den = math.sqrt(max(1e-12, 1 - asim * sharpe + (curt - 1) / 4 * sharpe**2))
    return nd.cdf((sharpe - sr0) * math.sqrt(n_obs - 1) / den)
