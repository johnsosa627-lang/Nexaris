"""Liga de bots: titulares (operan la cuenta) y suplentes (juegan de práctica al lado).

En esta versión TODO es con plata de mentira ("papel"): las operaciones se simulan sobre precios
reales de Binance que llegan en vivo, sin necesitar cuenta ni claves.
"""
from __future__ import annotations

import json
import math
import time

import numpy as np
import pandas as pd

from . import metricas as M
from .config import DATA_DIR, costo_ida_vuelta
from .indicadores import Cache
from .motor import correr

ARCHIVO = DATA_DIR / "liga.json"
CAPITAL_INICIAL = 15.0


def leer() -> dict:
    try:
        return json.loads(ARCHIVO.read_text())
    except Exception:
        return {"titulares": [], "suplentes": [], "jubilados": [], "pausado": False, "apagado": False,
                "inicio": int(time.time() * 1000)}


def guardar(liga: dict) -> None:
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARCHIVO.with_suffix(".tmp")
    tmp.write_text(json.dumps(liga, indent=1, default=str))
    tmp.replace(ARCHIVO)


def _kw(cfg):
    return {"costo_rt": costo_ida_vuelta(cfg), "funding_8h": cfg["costos"]["funding_8h"]}


def en_vivo(bot: dict, caches: dict, cfg: dict):
    """Operaciones que hizo el bot desde que entró a la liga (solo velas posteriores a su alta)."""
    e = bot["estrategia"]
    cache = caches.get((e["simbolo"], e["tf"]))
    if cache is None:
        return None
    ts = cache.df["ts"].to_numpy()
    ini = int(np.searchsorted(ts, bot["alta"]))
    return correr(e, cache, ini, None, tf=e["tf"], **_kw(cfg))


def _serie_diaria(bot: dict, caches: dict, cfg: dict) -> pd.Series:
    e = bot["estrategia"]
    cache = caches.get((e["simbolo"], e["tf"]))
    if cache is None:
        return pd.Series(dtype=float)
    res = correr(e, cache, 0, None, tf=e["tf"], **_kw(cfg))
    if not len(res.r):
        return pd.Series(dtype=float)
    dias = pd.to_datetime(res.ts_salida, unit="ms").floor("D")
    return pd.Series(res.r).groupby(dias).sum()


def correlacion(a: dict, b: dict, caches: dict, cfg: dict) -> float:
    sa, sb = _serie_diaria(a, caches, cfg), _serie_diaria(b, caches, cfg)
    j = pd.concat([sa, sb], axis=1).fillna(0)
    if len(j) < 30 or j.iloc[:, 0].std() == 0 or j.iloc[:, 1].std() == 0:
        return 0.0
    return float(j.corr().iloc[0, 1])


def _t(r_vivo: np.ndarray, media_esperada: float) -> float:
    if len(r_vivo) < 3 or np.std(r_vivo, ddof=1) == 0:
        return 0.0
    return (np.mean(r_vivo) - media_esperada) / (np.std(r_vivo, ddof=1) / math.sqrt(len(r_vivo)))


def agregar_candidatos(liga: dict, ganadoras: list[dict], cfg: dict) -> list[str]:
    ids = {b["id"] for b in liga["titulares"] + liga["suplentes"] + liga["jubilados"]}
    nuevos = []
    for g in ganadoras:
        if g["id"] in ids:
            continue
        bot = dict(g, alta=int(time.time() * 1000), rol="suplente")
        liga["suplentes"].append(bot)
        nuevos.append(g["id"])
    liga["suplentes"].sort(key=lambda b: b["puntaje"], reverse=True)
    liga["suplentes"] = liga["suplentes"][: cfg["liga"]["max_suplentes"]]
    return nuevos


def revisar(liga: dict, caches: dict, cfg: dict) -> list[str]:
    """Jubila a los que andan mal de verdad y asciende a los suplentes que lo merecen.
    Devuelve mensajes para mandar por Telegram."""
    L = cfg["liga"]
    avisos = []
    # 1) jubilaciones
    for grupo in ("titulares", "suplentes"):
        quedan = []
        for b in liga[grupo]:
            res = en_vivo(b, caches, cfg)
            r = res.r if res is not None else np.array([])
            eq = M.curva(r, cfg["riesgo"]["riesgo_por_operacion"])
            dd = M.max_drawdown(eq)
            esperado = b["metricas_datos_nuevos"]["expectancy_r"]
            motivo = None
            if len(r) >= 5 and dd > b["montecarlo"]["dd_p95"]:
                motivo = f"cayó {dd:.0%}, más que lo peor previsto ({b['montecarlo']['dd_p95']:.0%})"
            elif len(r) >= L["min_ops_para_juzgar"] and _t(r, esperado) < -2.5:
                motivo = "rinde mucho menos de lo que prometía (prueba estadística)"
            if motivo:
                b["baja"] = int(time.time() * 1000)
                b["motivo_baja"] = motivo
                liga["jubilados"].append(b)
                avisos.append(f"🪦 Se jubiló el bot {b['id']} ({grupo[:-1]}): {motivo}.")
            else:
                quedan.append(b)
        liga[grupo] = quedan
    # 2) ascensos
    sin_titulares = not liga["titulares"]
    for s in list(liga["suplentes"]):
        res = en_vivo(s, caches, cfg)
        r = res.r if res is not None else np.array([])
        listo = len(r) >= L["min_ops_para_ascender"] and r.mean() > 0
        if not (listo or sin_titulares):
            continue
        if any(abs(correlacion(s, t, caches, cfg)) > L["correlacion_max"] for t in liga["titulares"]):
            continue
        if len(liga["titulares"]) < L["max_titulares"]:
            entra, sale = True, None
        else:
            peor = min(liga["titulares"], key=lambda t: _media_vivo(t, caches, cfg))
            entra = listo and r.mean() > _media_vivo(peor, caches, cfg) + 0.1
            sale = peor
        if not entra:
            continue
        if sale is not None:
            liga["titulares"].remove(sale)
            sale["rol"] = "suplente"
            liga["suplentes"].append(sale)
            avisos.append(f"🔁 El bot {s['id']} reemplaza al {sale['id']} como titular.")
        else:
            avisos.append(f"⬆️ El bot {s['id']} pasa a titular.")
        liga["suplentes"].remove(s)
        s["rol"] = "titular"
        s["titular_desde"] = int(time.time() * 1000)
        liga["titulares"].append(s)
    return avisos


def _media_vivo(b, caches, cfg) -> float:
    res = en_vivo(b, caches, cfg)
    return float(res.r.mean()) if res is not None and len(res.r) else 0.0


def cuenta_papel(liga: dict, caches: dict, cfg: dict) -> dict:
    """Simula la cuenta de 15 USDT con los titulares, respetando frenos diario y total."""
    rk = cfg["riesgo"]
    ops = []
    for b in liga["titulares"]:
        desde = max(b["alta"], b.get("titular_desde", b["alta"]))
        e = b["estrategia"]
        cache = caches.get((e["simbolo"], e["tf"]))
        if cache is None:
            continue
        ts = cache.df["ts"].to_numpy()
        res = correr(e, cache, int(np.searchsorted(ts, desde)), None, tf=e["tf"], **_kw(cfg))
        for r, ei, t_sal in zip(res.r, res.entradas, res.ts_salida):
            ops.append((int(ts[ei]), int(t_sal), float(r), b["id"]))
    for b in liga["jubilados"]:
        if b.get("titular_desde"):
            e = b["estrategia"]
            cache = caches.get((e["simbolo"], e["tf"]))
            if cache is None:
                continue
            ts = cache.df["ts"].to_numpy()
            res = correr(e, cache, int(np.searchsorted(ts, b["titular_desde"])), None, tf=e["tf"], **_kw(cfg))
            for r, ei, t_sal in zip(res.r, res.entradas, res.ts_salida):
                if ts[ei] < b["baja"]:
                    ops.append((int(ts[ei]), int(t_sal), float(r), b["id"]))
    ops.sort()
    pausas = [(a, b or 10**15) for a, b in liga.get("pausas", [])]
    ops = [o for o in ops if not any(a <= o[0] < b for a, b in pausas)]
    capital = pico = CAPITAL_INICIAL
    hechas = []
    apagado = False
    for t_ent, t_sal, r, bid in ops:
        dia = t_ent // 86_400_000
        cerradas_hoy = [h for h in hechas if h["t_sal"] <= t_ent and h["t_sal"] // 86_400_000 == dia]
        perd_hoy = sum(1 for h in cerradas_hoy if h["r"] <= 0)
        res_hoy = sum(h["usdt"] for h in cerradas_hoy)
        if perd_hoy >= rk["freno_diario_perdidas"] or res_hoy <= -rk["freno_diario_pct"] * capital:
            continue  # freno diario: hoy no opera más
        usdt = capital * rk["riesgo_por_operacion"] * r
        capital += usdt
        pico = max(pico, capital)
        hechas.append({"t_ent": t_ent, "t_sal": t_sal, "r": r, "usdt": usdt, "bot": bid})
        if capital <= pico * (1 - rk["freno_total_pct"]):
            apagado = True   # el programa principal pausa todo; si el dueño reanuda, se arranca de cero el pico
            pico = capital
    hoy = int(time.time() * 1000) // 86_400_000
    de_hoy = [h for h in hechas if h["t_sal"] // 86_400_000 == hoy]
    return {"capital": round(capital, 2), "inicial": CAPITAL_INICIAL, "operaciones": len(hechas),
            "ganadas": sum(1 for h in hechas if h["r"] > 0), "hoy_ops": len(de_hoy),
            "hoy_ganadas": sum(1 for h in de_hoy if h["r"] > 0),
            "hoy_usdt": round(sum(h["usdt"] for h in de_hoy), 2), "freno_total": apagado,
            "max_dd": round(M.max_drawdown(np.cumsum([CAPITAL_INICIAL] + [h["usdt"] for h in hechas])[1:]
                                           / CAPITAL_INICIAL) if hechas else 0.0, 4)}
