"""Métricas de una lista de operaciones (el capital se reinvierte operación a operación)."""
import numpy as np
import pandas as pd

MS_ANIO = 365.25 * 86_400_000
TOPE = 999.0  # en lugar de "infinito" (ej: profit factor sin pérdidas)


def curva_capital(retornos: np.ndarray) -> np.ndarray:
    """Capital relativo empezando en 1, incluyendo el punto inicial."""
    return np.concatenate([[1.0], np.cumprod(1.0 + np.asarray(retornos, dtype=float))])


def max_drawdown_pct(curva: np.ndarray) -> float:
    pico = np.maximum.accumulate(curva)
    return float(((pico - curva) / pico).max() * 100) if len(curva) else 0.0


def estabilidad(curva: np.ndarray, tiempos: np.ndarray) -> float:
    """R² de la curva (en escala log) contra el tiempo; negativo si la curva baja. 1 = perfectamente pareja."""
    if len(curva) < 3 or np.any(curva <= 0):
        return 0.0
    y = np.log(curva)
    x = np.asarray(tiempos, dtype=float)
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return 0.0
    pendiente, origen = np.polyfit(x, y, 1)
    residuo = y - (pendiente * x + origen)
    r2 = 1 - (residuo ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return float(np.sign(pendiente) * max(r2, 0.0))


def racha_perdedora(retornos: np.ndarray) -> int:
    peor = actual = 0
    for x in retornos:
        actual = actual + 1 if x < 0 else 0
        peor = max(peor, actual)
    return peor


def calcular_metricas(ops: pd.DataFrame, ts_inicio: int, ts_fin: int) -> dict:
    n = len(ops)
    vacio = {"operaciones": 0, "ganadoras_pct": 0.0, "profit_factor": 0.0, "retorno_pct": 0.0,
             "cagr_pct": 0.0, "max_drawdown_pct": 0.0, "ret_dd": 0.0, "estabilidad": 0.0,
             "sharpe": 0.0, "expectativa_r": 0.0, "racha_perdedora": 0, "anios": {},
             "anios_positivos_pct": 0.0, "velas_promedio": 0.0, "operaciones_por_anio": 0.0}
    if n == 0:
        return vacio
    ret = ops["retorno"].to_numpy(dtype=float)
    curva = curva_capital(ret)
    ganancias, perdidas = ret[ret > 0].sum(), -ret[ret < 0].sum()
    retorno = (curva[-1] - 1) * 100
    dd = max_drawdown_pct(curva)
    anios_total = max((ts_fin - ts_inicio) / MS_ANIO, 1e-9)
    cagr = ((curva[-1]) ** (1 / anios_total) - 1) * 100 if curva[-1] > 0 else -100.0
    std = ret.std(ddof=1) if n > 1 else 0.0
    por_anio = n / anios_total
    sharpe = float(ret.mean() / std * np.sqrt(por_anio)) if std > 0 else 0.0

    anios = (pd.Series(ret, index=pd.to_datetime(ops["salida_ts"], unit="ms", utc=True).dt.year)
             .groupby(level=0).apply(lambda x: (np.prod(1 + x) - 1) * 100))
    tiempos = np.concatenate([[ts_inicio], ops["salida_ts"].to_numpy(dtype=float)])
    return {
        "operaciones": n,
        "ganadoras_pct": float((ret > 0).mean() * 100),
        "profit_factor": float(min(ganancias / perdidas, TOPE)) if perdidas > 0 else (TOPE if ganancias > 0 else 0.0),
        "retorno_pct": float(retorno),
        "cagr_pct": float(cagr),
        "max_drawdown_pct": dd,
        "ret_dd": float(min(retorno / dd, TOPE)) if dd > 0 else (TOPE if retorno > 0 else 0.0),
        "estabilidad": estabilidad(curva, tiempos),
        "sharpe": sharpe,
        "expectativa_r": float(ops["r"].mean()),
        "racha_perdedora": racha_perdedora(ret),
        "anios": {int(k): round(float(v), 2) for k, v in anios.items()},
        "anios_positivos_pct": float((anios > 0).mean() * 100),
        "velas_promedio": float(ops["velas"].mean()),
        "operaciones_por_anio": float(por_anio),
    }


def explicar(m: dict, capital: float = 15.0) -> str:
    """Resumen en lenguaje simple."""
    if m["operaciones"] == 0:
        return "La estrategia no hizo ninguna operación en este período."
    final = capital * (1 + m["retorno_pct"] / 100)
    return (
        f"Hizo {m['operaciones']} operaciones (unas {m['operaciones_por_anio']:.0f} por año) "
        f"y ganó el {m['ganadoras_pct']:.0f}% de las veces.\n"
        f"Con {capital:.0f} dólares habría terminado con {final:.2f} ({m['retorno_pct']:+.1f}%).\n"
        f"La peor caída desde un máximo fue de {m['max_drawdown_pct']:.1f}% "
        f"y llegó a perder {m['racha_perdedora']} veces seguidas.\n"
        f"Por cada dólar perdido ganó {m['profit_factor']:.2f} (profit factor); "
        f"ganancia/caída = {m['ret_dd']:.2f}; curva pareja = {m['estabilidad']:.2f} (1 es perfecta).\n"
        f"Resultado por año: " + ", ".join(f"{a}: {v:+.1f}%" for a, v in m["anios"].items())
    )
