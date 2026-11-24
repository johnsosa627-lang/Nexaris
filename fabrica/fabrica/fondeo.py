"""Modo examen de fondeo (ej. HyroTrader).

Solo LEE la cuenta y dice cuánto falta para la meta de ganancia y cuánto margen queda hasta los
límites del examen (pérdida diaria y pérdida total). NO cambia cómo opera el sistema: es un tablero.

Se prende con `fondeo.activo` en config.yaml, normalmente cuando corremos un examen real
(con EXCHANGE=bybit). Las reglas (meta, límites) se ponen en esa misma sección según la empresa.
"""
from typing import Optional

ICONO = {"aprobado": "🏆", "ok": "🟢", "cerca": "🟡", "roto": "🔴"}


def taper(caida_frac: float, limite_frac: float, piso: float = 0.25) -> float:
    """Freno gradual del drawdown: devuelve un factor (piso..1.0) para achicar el riesgo a medida que la
    cuenta cae desde su máximo. En el pico (caída 0) = 1.0; cerca del límite baja hasta `piso`. Así el
    sistema frena de a poco antes de reventar el examen, y le queda margen para recuperarse.
    `piso`=1.0 lo apaga (factor siempre 1.0)."""
    if limite_frac <= 0:
        return 1.0
    return max(piso, 1.0 - max(0.0, caida_frac) / limite_frac)


def estado(cfg: dict, cuenta: dict) -> Optional[dict]:
    """Números del examen a partir de la cuenta. None si el modo examen está apagado."""
    f = cfg.get("fondeo") or {}
    if not f.get("activo"):
        return None
    capital = float(f.get("capital", 100))
    equity = float(cuenta.get("equity", capital))
    pico = float(cuenta.get("pico", equity))
    inicio_dia = float(cuenta.get("inicio_dia", equity))

    meta_pct = float(f.get("meta_pct", 10.0))
    dia_pct = float(f.get("perdida_dia_pct", 4.0))
    total_pct = float(f.get("perdida_total_pct", 6.0))
    trailing = bool(f.get("trailing", True))

    ganancia_pct = (equity - capital) / capital * 100 if capital else 0.0
    falta_meta_pct = max(0.0, meta_pct - ganancia_pct)
    meta_usdt = capital * (1 + meta_pct / 100)

    # Límite diario: se mide desde el equity con que arrancó el día (como la mayoría de las empresas).
    perdida_hoy = max(0.0, inicio_dia - equity)
    limite_dia = capital * dia_pct / 100
    margen_dia = limite_dia - perdida_hoy

    # Límite total: trailing desde el pico, o fijo desde el capital inicial.
    referencia = pico if trailing else capital
    piso_total = referencia * (1 - total_pct / 100)
    margen_total = equity - piso_total
    limite_total = referencia * total_pct / 100

    aprobado = ganancia_pct >= meta_pct
    roto = margen_dia <= 0 or margen_total <= 0
    cerca = margen_dia <= limite_dia * 0.25 or margen_total <= limite_total * 0.25
    nombre = "aprobado" if aprobado else "roto" if roto else "cerca" if cerca else "ok"
    return {
        "empresa": f.get("empresa", ""), "fase": f.get("fase", ""),
        "capital": capital, "equity": equity, "ganancia_pct": ganancia_pct,
        "falta_meta_pct": falta_meta_pct, "meta_usdt": meta_usdt,
        "margen_dia": margen_dia, "limite_dia": limite_dia,
        "margen_total": margen_total, "piso_total": piso_total, "trailing": trailing,
        "estado": nombre,
    }


def texto(cfg: dict, cuenta: dict) -> str:
    e = estado(cfg, cuenta)
    if e is None:
        return ("🎓 El modo examen de fondeo está APAGADO. Se prende en config.yaml (fondeo.activo) "
                "cuando estemos corriendo un examen real.")
    ico = ICONO.get(e["estado"], "")
    meta = (f"Meta: ganar {e['falta_meta_pct']:.2f}% más (llegar a {e['meta_usdt']:.2f} USDT)"
            if e["falta_meta_pct"] > 0 else "Meta: ✅ ¡alcanzada!")
    lineas = [f"🎓 EXAMEN DE FONDEO — {e['empresa']} ({e['fase']})  {ico}",
              f"Cuenta: {e['equity']:.2f} de {e['capital']:.2f} USDT ({e['ganancia_pct']:+.2f}%)",
              meta,
              f"Margen HOY: {e['margen_dia']:+.2f} USDT antes del límite diario",
              f"Margen TOTAL: {e['margen_total']:+.2f} USDT antes del límite"
              f"{' (sigue al pico)' if e['trailing'] else ''}"]
    if e["estado"] == "roto":
        lineas.append("🔴 Se pasó un límite: el examen se daría por perdido.")
    elif e["estado"] == "cerca":
        lineas.append("🟡 Ojo: estás cerca de un límite, cuidado.")
    elif e["estado"] == "aprobado":
        lineas.append("🏆 ¡Meta alcanzada! Confirmá las reglas de la empresa para pasar de fase o cobrar.")
    return "\n".join(lineas)
