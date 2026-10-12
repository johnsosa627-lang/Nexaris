"""Reglas de protección de la cuenta y pruebas estadísticas de la liga (funciones puras)."""
import math
from typing import Optional, Tuple

import numpy as np


# ------------------------------------------------------------------ tamaño y riesgo
def capital_base(capital_configurado: float, equity: float) -> float:
    """Capital sobre el que se calcula el riesgo. Las ganancias NUNCA lo aumentan solo:
    para arriesgar más, hay que subir `capital_inicial` a mano. Las pérdidas sí lo achican."""
    return max(0.0, min(capital_configurado, equity))


def tamano(riesgo_usdt: float, distancia_stop: float, precio: float, capital: float, apalancamiento_max: float,
           ajustar=None, min_cantidad: Optional[float] = None, min_nocional: Optional[float] = None) -> Tuple[float, str]:
    """Cantidad para perder `riesgo_usdt` si toca el stop, con tope de apalancamiento.
    Devuelve (cantidad, "") o (0, motivo) si no se puede operar."""
    if distancia_stop <= 0 or precio <= 0 or riesgo_usdt <= 0:
        return 0.0, "datos inválidos para calcular el tamaño"
    cantidad = min(riesgo_usdt / distancia_stop, capital * apalancamiento_max / precio)
    if ajustar is not None:
        cantidad = ajustar(cantidad)
    if cantidad <= 0:
        return 0.0, "la cantidad queda en 0 con este capital"
    if min_cantidad and cantidad < min_cantidad:
        return 0.0, f"la cantidad ({cantidad:g}) es menor al mínimo de Binance ({min_cantidad:g})"
    if min_nocional and cantidad * precio < min_nocional:
        return 0.0, (f"la operación sería de {cantidad * precio:.2f} USDT y Binance exige al menos "
                     f"{min_nocional:g} USDT")
    return cantidad, ""


def riesgo_abierto_permitido(riesgo_abierto: float, riesgo_nuevo: float, capital: float, max_pct: float) -> bool:
    return riesgo_abierto + riesgo_nuevo <= capital * max_pct / 100 + 1e-9


def freno_diario(pnl_hoy: float, perdidas_seguidas: int, capital_inicio_dia: float, max_perdida_pct: float,
                 max_seguidas: int) -> Optional[str]:
    if capital_inicio_dia > 0 and -pnl_hoy >= capital_inicio_dia * max_perdida_pct / 100:
        return f"perdió {-pnl_hoy:.2f} USDT hoy ({max_perdida_pct}% o más)"
    if perdidas_seguidas >= max_seguidas:
        return f"{perdidas_seguidas} operaciones perdidas seguidas hoy"
    return None


def freno_total(equity: float, pico: float, max_caida_pct: float) -> bool:
    return pico > 0 and (pico - equity) / pico * 100 >= max_caida_pct


# ------------------------------------------------------------------ estadística
def drawdown_pct(retornos) -> float:
    """Peor caída (en % del capital) de una serie de retornos con tamaño fijo."""
    if len(retornos) == 0:
        return 0.0
    curva = np.concatenate([[0.0], np.cumsum(retornos)])
    return float((np.maximum.accumulate(curva) - curva).max() * 100)


def z_contra_backtest(vivo, backtest) -> float:
    """Cuántos 'desvíos' está el promedio en vivo por debajo (negativo) de lo que prometía el backtest."""
    vivo, backtest = np.asarray(vivo, float), np.asarray(backtest, float)
    if len(vivo) == 0 or len(backtest) < 2 or backtest.std(ddof=1) == 0:
        return 0.0
    return float((vivo.mean() - backtest.mean()) / (backtest.std(ddof=1) / math.sqrt(len(vivo))))


def t_welch(a, b) -> float:
    """Qué tan claramente el promedio de `a` supera al de `b` (t de Welch)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 2 or len(b) < 2:
        return 0.0
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    if va + vb == 0:
        return 0.0
    return float((a.mean() - b.mean()) / math.sqrt(va + vb))


def correlacion(diario_a: dict, diario_b: dict) -> float:
    """Correlación de los resultados diarios en el período en que ambas existían (0 si no hay datos)."""
    if not diario_a or not diario_b:
        return 0.0
    desde = max(min(diario_a), min(diario_b))
    hasta = min(max(diario_a), max(diario_b))
    dias = sorted(d for d in set(diario_a) | set(diario_b) if desde <= d <= hasta)
    if len(dias) < 10:
        return 0.0
    a = np.array([diario_a.get(d, 0.0) for d in dias])
    b = np.array([diario_b.get(d, 0.0) for d in dias])
    if a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])
