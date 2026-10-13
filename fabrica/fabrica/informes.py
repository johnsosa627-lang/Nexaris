"""Informes en lenguaje simple (pensados para leer en el celular / Telegram)."""
import json
import os

from .filtros import FILTROS

NOMBRES_TF = {"15m": "velas de 15 minutos", "1h": "velas de 1 hora", "4h": "velas de 4 horas"}


def _moneda(simbolo):
    return simbolo.split("/")[0]


def tarjeta(registro: dict, capital: float = 15.0) -> str:
    """Ficha de una estrategia: qué hace, cómo le fue y qué riesgos tiene."""
    m = registro.get("metricas_trabajo") or registro.get("metricas_creacion") or {}
    mc = registro.get("montecarlo") or {}
    lineas = [
        ("🧪 EN PRUEBA (pasó con filtros flojos: solo practica, nunca con plata real)\n"
         if registro.get("nivel") == "exploracion" else "") +
        f"📈 Estrategia {registro['id']} — {_moneda(registro['simbolo'])}, {NOMBRES_TF.get(registro['tf'], registro['tf'])}",
        f"Qué hace: {registro['explicacion']}",
    ]
    if m:
        final = capital * (1 + m.get("retorno_pct", 0) / 100)
        lineas.append(
            f"En el pasado: {m['operaciones']} operaciones, ganó el {m['ganadoras_pct']:.0f}% de las veces. "
            f"Con {capital:.0f} dólares habría terminado con {final:.2f}. "
            f"Por cada dólar perdido ganó {m['profit_factor']:.2f}.")
        lineas.append(
            f"Lo malo: su peor caída fue de {m['max_drawdown_pct']:.1f}% y llegó a perder "
            f"{m['racha_perdedora']} veces seguidas. Eso es normal en esta estrategia y no es motivo para apagarla.")
    if mc:
        lineas.append(f"Monte Carlo: ganó en el {mc['pct_ganadoras']:.0f}% de {mc['simulaciones']} simulaciones; "
                      f"en el peor 5% de los casos la caída llegaría a {mc['drawdown_p95_pct']:.1f}%.")
    ex = registro.get("examen")
    if ex:
        em = ex["metricas"]
        if ex["aprobada"]:
            lineas.append(f"✅ Examen final (meses nunca vistos): APROBÓ. {em['operaciones']} operaciones, "
                          f"resultado {em['retorno_pct']:+.1f}%, peor caída {em['max_drawdown_pct']:.1f}%.")
        else:
            lineas.append(f"❌ Examen final: REPROBÓ ({'; '.join(ex['motivos'])}). Queda descartada para siempre.")
    else:
        lineas.append("⏳ Examen final: pendiente.")
    return "\n".join(lineas)


def informe_ciclo(cfg: dict, carpeta_ciclo: str) -> str:
    """Informe de un ciclo: embudo de filtros + examen final + estado del banco."""
    from .examen import banco
    with open(os.path.join(carpeta_ciclo, "embudo.json"), encoding="utf-8") as f:
        resumen = json.load(f)
    e = resumen["embudo"]
    aprobadas = []
    carpeta = os.path.join(carpeta_ciclo, "aprobadas")
    if os.path.isdir(carpeta):
        for n in sorted(os.listdir(carpeta)):
            with open(os.path.join(carpeta, n), encoding="utf-8") as f:
                aprobadas.append(json.load(f))
    capital = cfg["riesgo"]["capital_inicial"]
    examinadas = [a for a in aprobadas if a.get("examen")]
    pasaron = [a for a in examinadas if a["examen"]["aprobada"]]

    lineas = [f"🏭 INFORME DE LA FÁBRICA — {resumen['ciclo']}", "",
              f"La computadora inventó y probó {e['inventadas']} estrategias."
              + (f" ({e['ya_examinadas_antes']} ya habían rendido examen antes y no se repiten.)"
                 if e.get("ya_examinadas_antes") else ""),
              f"Las {e['candidatas']} mejores pasaron por el colador:"]
    for clave, nombre, _ in FILTROS:
        lineas.append(f"  {clave[0]}. {nombre}: pasaron {e[clave]}")
    if e.get("aprobadas_exploracion"):
        lineas.append(f"  🧪 Además, {e['aprobadas_exploracion']} pasaron con los filtros flojos de exploración (solo práctica)")
    lineas.append(f"  Examen final: {len(pasaron)} de {len(examinadas)} aprobaron")
    lineas.append("")
    if pasaron:
        lineas.append(f"🎉 {len(pasaron)} estrategia(s) nueva(s) entran al banco (candidatas a operar con plata de mentira):")
        for a in pasaron:
            lineas += ["", tarjeta(a, capital)]
    elif examinadas:
        lineas.append("Ninguna aprobó el examen final. Se descartan: mejor eso que arriesgar plata en algo que no funciona.")
    else:
        lineas.append("Ninguna estrategia llegó al examen final en este ciclo. Es normal: el colador es exigente a propósito.")
    reprobadas = [a for a in examinadas if not a["examen"]["aprobada"]]
    if reprobadas:
        lineas += ["", "Reprobaron el examen final:"]
        lineas += [f"  ❌ {a['id']} ({_moneda(a['simbolo'])} {a['tf']}): {'; '.join(a['examen']['motivos'])}" for a in reprobadas]
    total_banco = banco(cfg)
    lineas += ["", f"📦 Banco total: {len(total_banco)} estrategia(s) que aprobaron todo, listas para la liga."]
    texto = "\n".join(lineas)
    with open(os.path.join(carpeta_ciclo, "informe.txt"), "w", encoding="utf-8") as f:
        f.write(texto)
    return texto
