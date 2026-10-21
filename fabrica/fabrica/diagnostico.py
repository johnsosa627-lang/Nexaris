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
    # En vivo cuenta toda vela que CERRÓ después de que el bot entró (la que estaba abierta en ese momento también)
    en_vivo = ((velas["ts"] + _paso(velas)) > desde).to_numpy()
    largo, corto = senales(Contexto(velas, externos), bot["estrategia"])
    n_historia = int(((largo | corto) & en_vivo).sum())
    # como en vivo: vela por vela, solo con las últimas `historia` velas
    idx = [i for i in range(len(velas)) if en_vivo[i]][-MAX_VELAS_VIVO:]
    n_vivo, momentos = 0, []
    for i in idx:
        ini = max(0, i + 1 - historia)
        ventana = velas.iloc[ini:i + 1].reset_index(drop=True)
        ext = {k: v[ini:i + 1] for k, v in externos.items()} if externos else None
        lado, _ = senal_ultima_vela(bot["estrategia"], ventana, ext)
        if lado:
            n_vivo += 1
            momentos.append(int(velas["ts"].iloc[i]) + _paso(velas))  # la señal se ve al cerrar la vela
    return {"id": bot["id"], "mercado": f"{bot['simbolo'].split('/')[0]} {bot['tf']}", "velas_en_vivo": int(en_vivo.sum()),
            "senales_historia": n_historia, "senales_vivo": n_vivo, "revisadas_vivo": len(idx),
            "operaciones": len(bot.get("trades") or []) + (1 if bot.get("posicion") else 0),
            "momentos": momentos[-3:], "perdidas": (bot.get("senales_perdidas") or [])[-3:]}


def _paso(velas) -> int:
    return int(velas["ts"].diff().median()) if len(velas) > 1 else 0


def _hora(ms: int) -> str:
    return pd.Timestamp(ms, unit="ms", tz="UTC").strftime("%d/%m %H:%M UTC")


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
        if marca == "⚠️":
            if r.get("momentos"):
                lineas.append("   señales: " + ", ".join(_hora(m) for m in r["momentos"]))
            for p in r.get("perdidas") or []:
                lineas.append(f"   no operó el {_hora(p['ts'])}: {p['motivo']}")
    if problemas:
        lineas.append(f"\n⚠️ {problemas} bot(s) tuvieron señales y no operaron. Si dice el motivo (por ejemplo, una pausa "
                      "del radar), está bien. Si no dice nada, hay algo que revisar. Los titulares respetan las pausas del "
                      "radar y los frenos; los suplentes no.")
    else:
        lineas.append("\nNinguna señal quedó sin operar: si no hubo operaciones es porque no hubo señales.")
    return "\n".join(lineas)
