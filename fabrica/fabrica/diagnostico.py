"""Diagnóstico de los bots en vivo: ¿hubo señales que deberían haber abierto operaciones?

Para cada titular y suplente recalcula, con los datos guardados, las señales desde que entró en vivo, de dos formas:
  - "historia": con toda la historia (como en las pruebas de la fábrica),
  - "vivo": vela por vela con solo las últimas velas, igual que hace el bot en vivo.
Si hubo señales y el bot no operó, hay un problema en la parte en vivo. No toca la plata ni la liga.
"""
import pandas as pd

from .bots import senal_ultima_vela, usa_externos
from .datos import SIMBOLO_LIDER, cargar_funding, cargar_miedo_codicia, cargar_velas, externos_para
from .estrategia import Contexto, senales

MAX_VELAS_VIVO = 400  # cuántas velas recientes se recorren como en vivo (alcanza para varios días en 15m)


def _ms(iso: str) -> int:
    t = pd.Timestamp(iso)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return int(t.timestamp() * 1000)


def diagnosticar_bot(cfg: dict, bot: dict, historia: int = 1000) -> dict:
    carpeta = cfg["datos"]["carpeta"]
    velas = cargar_velas(carpeta, bot["simbolo"], bot["tf"])
    if velas.empty:
        return {"id": bot["id"], "error": "no hay datos guardados"}
    externos = None
    if usa_externos(bot["estrategia"]):
        externos = externos_para(velas["ts"].to_numpy(), bot["tf"], cargar_funding(carpeta, bot["simbolo"]),
                                 cargar_velas(carpeta, SIMBOLO_LIDER, bot["tf"]), cargar_miedo_codicia(carpeta))
    desde = _ms(bot["desde"])
    en_vivo = (velas["ts"] >= desde).to_numpy()
    largo, corto = senales(Contexto(velas, externos), bot["estrategia"])
    n_historia = int(((largo | corto) & en_vivo).sum())
    # como en vivo: vela por vela, solo con las últimas `historia` velas
    idx = [i for i in range(len(velas)) if en_vivo[i]][-MAX_VELAS_VIVO:]
    n_vivo = 0
    for i in idx:
        ini = max(0, i + 1 - historia)
        ventana = velas.iloc[ini:i + 1].reset_index(drop=True)
        ext = {k: v[ini:i + 1] for k, v in externos.items()} if externos else None
        lado, _ = senal_ultima_vela(bot["estrategia"], ventana, ext)
        n_vivo += 1 if lado else 0
    return {"id": bot["id"], "mercado": f"{bot['simbolo'].split('/')[0]} {bot['tf']}", "velas_en_vivo": int(en_vivo.sum()),
            "senales_historia": n_historia, "senales_vivo": n_vivo, "revisadas_vivo": len(idx),
            "operaciones": len(bot.get("trades") or []) + (1 if bot.get("posicion") else 0)}


def diagnosticar(cfg: dict, bots: list, historia: int = 1000) -> list:
    return [diagnosticar_bot(cfg, b, historia) for b in bots if b.get("rol") in ("titular", "suplente")]


def texto(resultados: list) -> str:
    lineas = ["🔬 Diagnóstico: señales desde que cada bot entró en vivo (recalculadas con los datos guardados)"]
    problemas = 0
    for r in resultados:
        if r.get("error"):
            lineas.append(f"• {r['id']}: {r['error']}")
            continue
        marca = "✅"
        if r["senales_vivo"] > 0 and r["operaciones"] == 0:
            marca, problemas = "⚠️", problemas + 1
        lineas.append(f"{marca} {r['id']} ({r['mercado']}): {r['senales_vivo']} señales en vivo, "
                      f"{r['senales_historia']} con toda la historia, {r['operaciones']} operaciones")
    if problemas:
        lineas.append(f"\n⚠️ {problemas} bot(s) tuvieron señales y no operaron: hay algo que revisar.")
    else:
        lineas.append("\nNinguna señal quedó sin operar: si no hubo operaciones es porque no hubo señales.")
    return "\n".join(lineas)
