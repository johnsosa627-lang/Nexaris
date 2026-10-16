"""Chequeo de salud: la fábrica se revisa sola y avisa si algo no está funcionando como debería.

Nació de problemas reales que no se veían desde afuera: historia de precios cortada, ciclos que no
inventaban nada y ciclos que no volvían a correr. Ninguna de estas revisiones toca la plata ni la liga.
"""
import json
import os
import shutil
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from .datos import cargar_velas, revisar_calidad, tf_ms

DIA_MS = 86_400_000
MIN_DIAS_HISTORIA = 365        # con menos de un año de datos, la fábrica no tiene con qué trabajar
MAX_FALTANTES = 0.02           # más de 2% de velas faltantes = datos rotos
MAX_DIAS_SIN_CICLO = 8         # el ciclo es semanal: más de 8 días sin correr = algo lo frena
MIN_DISCO_LIBRE_GB = 2.0


def revisar_datos(cfg: dict, ahora_ms: int) -> tuple:
    problemas, ok = [], []
    d = cfg["datos"]
    inicio_pedido = int(pd.Timestamp(d["desde"], tz="UTC").timestamp() * 1000)
    for simbolo in d["simbolos"]:
        for tf in d["temporalidades"]:
            nombre = f"{simbolo.split('/')[0]} {tf}"
            df = cargar_velas(d["carpeta"], simbolo, tf)
            if df.empty:
                problemas.append(f"{nombre}: no hay datos de precios.")
                continue
            q = revisar_calidad(df, tf)
            primero, ultimo = int(df["ts"].iloc[0]), int(df["ts"].iloc[-1])
            dias = (ultimo - primero) / DIA_MS
            esperadas = (ultimo - primero) // tf_ms(tf) + 1
            faltan = 1 - len(df) / esperadas if esperadas else 0
            if dias < MIN_DIAS_HISTORIA:
                problemas.append(f"{nombre}: la historia es muy corta ({dias:.0f} días, desde {q['desde']} hasta {q['hasta']}).")
            elif primero > inicio_pedido + 60 * DIA_MS and ahora_ms - inicio_pedido > 400 * DIA_MS:
                problemas.append(f"{nombre}: la historia empieza recién el {q['desde']} (se pidió desde {d['desde']}).")
            if ahora_ms - ultimo > 2 * DIA_MS:
                problemas.append(f"{nombre}: los datos están viejos (última vela del {q['hasta']}).")
            if faltan > MAX_FALTANTES:
                problemas.append(f"{nombre}: faltan {faltan:.0%} de las velas.")
            if q["duplicadas"] or q["incoherentes"]:
                problemas.append(f"{nombre}: {q['duplicadas']} velas repetidas y {q['incoherentes']} con precios imposibles.")
            if dias >= MIN_DIAS_HISTORIA and faltan <= MAX_FALTANTES:
                ok.append(f"{nombre}: {len(df)} velas ({q['desde']} a {q['hasta']})")
    return problemas, ok


def _ultimo_ciclo(cfg: dict) -> Optional[tuple]:
    """(fecha del último ciclo en ms, estrategias inventadas) o None si nunca corrió."""
    salida = cfg["salida"]["carpeta"]
    try:
        with open(os.path.join(salida, "ultimo_ciclo.txt"), encoding="utf-8") as f:
            nombre = f.read().strip()
        fecha = datetime.strptime(nombre, "ciclo_%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
        with open(os.path.join(salida, nombre, "embudo.json"), encoding="utf-8") as f:
            inventadas = int(json.load(f)["embudo"].get("inventadas", 0))
        return int(fecha.timestamp() * 1000), inventadas
    except (OSError, ValueError, KeyError):
        return None


def revisar_fabrica(cfg: dict, ahora_ms: int, ciclo_en_curso: bool, prendida_desde_ms: int) -> tuple:
    problemas, ok = [], []
    ultimo = _ultimo_ciclo(cfg)
    if ultimo is None:
        if not ciclo_en_curso and ahora_ms - prendida_desde_ms > DIA_MS:
            problemas.append("La fábrica nunca terminó un ciclo y lleva más de un día prendida.")
        return problemas, ok
    fecha, inventadas = ultimo
    dias = (ahora_ms - fecha) / DIA_MS
    if inventadas == 0 and not ciclo_en_curso:
        problemas.append("El último ciclo no inventó ninguna estrategia (casi siempre: faltan datos). Se reintenta solo; "
                         "también podés mandar /ciclo.")
    if dias > MAX_DIAS_SIN_CICLO and not ciclo_en_curso:
        problemas.append(f"Hace {dias:.0f} días que la fábrica no corre un ciclo (debería ser semanal).")
    if inventadas:
        ok.append(f"Último ciclo hace {dias:.1f} días: inventó {inventadas} estrategias")
    return problemas, ok


def revisar_bots(bots: list, ahora_ms: int) -> tuple:
    """¿Los bots reciben velas? ¿Operan más o menos tan seguido como prometía su backtest?"""
    problemas, ok = [], []
    activos = [b for b in bots if b.get("rol") in ("titular", "suplente")]
    al_dia = 0
    for b in activos:
        nombre = f"{b['id']} ({b['simbolo'].split('/')[0]} {b['tf']})"
        paso = tf_ms(b["tf"])
        desde = pd.Timestamp(b["desde"]).tz_localize("UTC") if pd.Timestamp(b["desde"]).tzinfo is None \
            else pd.Timestamp(b["desde"])
        vivo_ms = ahora_ms - int(desde.timestamp() * 1000)
        ultima = int(b.get("ultima_vela_ts") or 0)
        if ultima == 0:
            if vivo_ms > 3 * paso + 10 * 60_000:
                problemas.append(f"{nombre}: todavía no procesó ninguna vela.")
            continue
        if ahora_ms - (ultima + paso) > 3 * paso + 10 * 60_000:
            problemas.append(f"{nombre}: no recibe velas nuevas desde hace {(ahora_ms - ultima) / 3_600_000:.0f} horas.")
            continue
        al_dia += 1
        # frecuencia esperada según el backtest (operaciones por día)
        dias_bt = sorted(b.get("retornos_diarios") or {})
        n_bt = len(b.get("r_backtest") or [])
        if len(dias_bt) >= 2 and n_bt:
            span = (pd.Timestamp(dias_bt[-1]) - pd.Timestamp(dias_bt[0])).days or 1
            esperadas = n_bt / span * vivo_ms / DIA_MS
            hechas = len(b.get("trades") or []) + (1 if b.get("posicion") else 0)
            if esperadas >= 4 and hechas == 0:
                problemas.append(f"{nombre}: según sus pruebas ya debería haber operado unas {esperadas:.0f} veces y no "
                                 "operó ninguna. Puede ser un error o que el mercado cambió.")
    if activos:
        ok.append(f"{al_dia} de {len(activos)} bots reciben velas al día")
    return problemas, ok


def revisar_disco(carpeta: str) -> tuple:
    try:
        libre = shutil.disk_usage(carpeta if os.path.isdir(carpeta) else "/").free / 1e9
    except OSError:
        return [], []
    if libre < MIN_DISCO_LIBRE_GB:
        return [f"Queda poco disco libre: {libre:.1f} GB."], []
    return [], [f"Disco libre: {libre:.0f} GB"]


def chequeo(cfg: dict, ahora_ms: Optional[int] = None, ciclo_en_curso: bool = False,
            prendida_desde_ms: Optional[int] = None, bots: Optional[list] = None) -> dict:
    ahora_ms = ahora_ms or int(time.time() * 1000)
    problemas, ok = [], []
    for p, o in (revisar_datos(cfg, ahora_ms),
                 revisar_fabrica(cfg, ahora_ms, ciclo_en_curso, prendida_desde_ms or ahora_ms),
                 revisar_disco(cfg["datos"]["carpeta"]),
                 revisar_bots(bots or [], ahora_ms)):
        problemas += p
        ok += o
    version = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")
    if os.path.exists(version):
        with open(version, encoding="utf-8") as f:
            ok.append(f"Versión del programa armada el {f.read().strip()}")
    return {"problemas": problemas, "ok": ok}


def texto(r: dict, completo: bool = True) -> str:
    if not r["problemas"]:
        cabeza = "🩺 Chequeo de salud: todo en orden ✅"
    else:
        cabeza = f"🩺 Chequeo de salud: encontré {len(r['problemas'])} problema(s) ⚠️\n" + \
                 "\n".join(f"• {p}" for p in r["problemas"])
    if completo and r["ok"]:
        cabeza += "\n\nFunciona bien:\n" + "\n".join(f"✓ {o}" for o in r["ok"])
    return cabeza
