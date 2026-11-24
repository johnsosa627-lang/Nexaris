"""¿El sistema PASARÍA un examen de fondeo? Prueba con el historial (backtest), sin tocar nada en vivo.

Idea: junta los retornos diarios del equipo de titulares (del backtest sobre los meses guardados) y
simula las reglas del examen (meta de ganancia, pérdida diaria, pérdida total trailing) ARRANCANDO EN
CADA DÍA posible. Así no depende de la suerte del día de arranque: dice en qué % de los arranques pasaría.

    python -m fabrica.probar_examen            # usa las reglas de config (fondeo) y el banco actual

NO corre en vivo, no toca Binance ni Bybit, no gasta memoria del servicio: es una corrida y termina.
Es una APROXIMACIÓN honesta (suma los retornos diarios de los bots; no modela el tope de 3% abierto a
la vez), pero es exigente: usa meses reales y prueba muchos arranques.
"""
import logging

log = logging.getLogger("fabrica")


def simular(dias, meta_pct, dia_pct, total_pct, desde=0):
    """Simula un examen arrancando en el índice `desde`. `dias` = lista de (fecha, retorno_fracción).

    Devuelve (estado, info): estado en {"aprobado","roto_dia","roto_total","sin_terminar"}.
    equity es la ganancia acumulada en fracción (0 = inicio, 0.10 = +10%).
    """
    equity = 0.0
    pico = 0.0
    meta = meta_pct / 100.0
    peor_dia = 0.0   # mayor pérdida en un día (fracción, positiva)
    peor_total = 0.0  # mayor caída desde el pico (fracción, positiva)
    for _, ret in dias[desde:]:
        equity += ret
        if ret < 0:
            peor_dia = max(peor_dia, -ret)
        if -ret >= dia_pct / 100.0:                     # rompió el límite diario
            return "roto_dia", {"equity": equity, "peor_dia": max(peor_dia, -ret), "peor_total": peor_total}
        pico = max(pico, equity)
        peor_total = max(peor_total, pico - equity)
        if (pico - equity) >= total_pct / 100.0:        # rompió el límite total (trailing desde el pico)
            return "roto_total", {"equity": equity, "peor_dia": peor_dia, "peor_total": pico - equity}
        if equity >= meta:                              # llegó a la meta: aprobado
            return "aprobado", {"equity": equity, "peor_dia": peor_dia, "peor_total": peor_total}
    return "sin_terminar", {"equity": equity, "peor_dia": peor_dia, "peor_total": peor_total}


def simular_rolling(dias, meta_pct, dia_pct, total_pct):
    """Corre el examen arrancando en cada día y resume. Devuelve un dict con el conteo y lo peor visto."""
    conteo = {"aprobado": 0, "roto_dia": 0, "roto_total": 0, "sin_terminar": 0}
    peor_dia = peor_total = 0.0
    arranques = max(1, len(dias))
    for i in range(arranques):
        estado, info = simular(dias, meta_pct, dia_pct, total_pct, desde=i)
        conteo[estado] += 1
        peor_dia = max(peor_dia, info["peor_dia"])
        peor_total = max(peor_total, info["peor_total"])
    pasa = conteo["aprobado"]
    rompe = conteo["roto_dia"] + conteo["roto_total"]
    return {"conteo": conteo, "arranques": arranques, "pct_aprueba": 100.0 * pasa / arranques,
            "pct_rompe": 100.0 * rompe / arranques, "peor_dia_pct": peor_dia * 100, "peor_total_pct": peor_total * 100}


def _variedad(registros, n):
    """Elige hasta n estrategias del banco cubriendo monedas/temporalidades distintas (como la liga)."""
    vistos, equipo = set(), []
    for r in registros:                 # el banco ya viene ordenado por desempeño
        clave = (r.get("simbolo"), r.get("tf"))
        if clave not in vistos:
            vistos.add(clave)
            equipo.append(r)
        if len(equipo) >= n:
            break
    if len(equipo) < n:                  # si faltan, completo con los que siguen
        for r in registros:
            if r not in equipo:
                equipo.append(r)
            if len(equipo) >= n:
                break
    return equipo[:n]


def serie_combinada(equipo):
    """Junta los retornos diarios del equipo en una sola serie (fecha -> suma), ordenada por fecha."""
    porfecha = {}
    for r in equipo:
        for fecha, ret in (r.get("retornos_diarios") or {}).items():
            porfecha[fecha] = porfecha.get(fecha, 0.0) + float(ret)
    return [(f, porfecha[f]) for f in sorted(porfecha)]


def texto(cfg):
    from .examen import banco
    f = cfg.get("fondeo") or {}
    meta = float(f.get("meta_pct", 10.0))
    dia = float(f.get("perdida_dia_pct", 4.0))
    total = float(f.get("perdida_total_pct", 6.0))
    empresa, fase = f.get("empresa", "HyroTrader"), f.get("fase", "1 paso")
    n = int((cfg.get("liga") or {}).get("max_titulares", 8))

    registros = [r for r in banco(cfg) if r.get("retornos_diarios")]
    if not registros:
        return ("🎓 Prueba del examen: todavía no hay estrategias en el banco con historial para probar. "
                "Esperá a que la fábrica llene el banco.")
    equipo = _variedad(registros, n)
    dias = serie_combinada(equipo)
    if not dias:
        return "🎓 Prueba del examen: el equipo no tiene retornos diarios para simular."

    res = simular_rolling(dias, meta, dia, total)
    lineas = [f"🎓 PRUEBA DEL EXAMEN — {empresa} ({fase})",
              f"Reglas: ganar {meta:.0f}%, sin perder {dia:.0f}% en un día ni {total:.0f}% total (trailing).",
              f"Equipo: {len(equipo)} estrategias · {len(dias)} días de historial · {res['arranques']} arranques probados.",
              "",
              f"✅ Pasaría el examen en el {res['pct_aprueba']:.0f}% de los arranques.",
              f"🔴 Lo rompería en el {res['pct_rompe']:.0f}%.",
              f"Peor día: −{res['peor_dia_pct']:.2f}% (límite {dia:.0f}%) · "
              f"peor caída total: −{res['peor_total_pct']:.2f}% (límite {total:.0f}%)."]
    if res["peor_dia_pct"] >= dia or res["peor_total_pct"] >= total:
        lineas.append("⚠️ En algún momento tocó un límite: hay que mejorar antes de pagar el examen.")
    elif res["pct_aprueba"] >= 60:
        lineas.append("👍 Viene sólido: pasaría la mayoría de las veces y nunca tocó un límite en el historial.")
    else:
        lineas.append("🟡 No rompe límites, pero tarda en llegar a la meta: conviene más historial antes de pagar.")
    lineas.append("(Es una prueba con datos pasados; no garantiza el futuro. Sin tocar nada en vivo.)")
    return "\n".join(lineas)


def main():
    from .config import cargar_config
    print(texto(cargar_config()))


if __name__ == "__main__":
    main()
