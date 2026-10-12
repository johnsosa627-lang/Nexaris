"""Una estrategia es una 'receta': condiciones de entrada + salidas (stop-loss obligatorio).

Se guarda como diccionario/JSON. Ejemplo:
{"lado": "long", "condiciones": [{"tipo": "rsi", "n": 14, "op": "<", "x": 30}],
 "sl_atr": 2.0, "tp_atr": 3.0, "max_barras": 48, "atr_n": 14}
"""
from __future__ import annotations

import hashlib
import json
import random

import numpy as np

from .indicadores import Cache

SERIES = ["ema", "sma"]
TIPOS = ["cruce", "comparar", "rsi", "adx", "ruptura", "volumen", "bollinger", "macd", "esto", "cci"]

# Rangos de cada número (para inventar y para mutar)
RANGOS = {
    "n": (5, 100), "n2": (10, 200), "x_rsi": (15, 85), "x_adx": (15, 40), "n_rup": (10, 100),
    "x_vol": (0.8, 3.0), "k": (1.5, 3.0), "x_esto": (10, 90), "x_cci": (-200, 200),
    "sl_atr": (0.8, 4.0), "tp_atr": (0.8, 8.0), "max_barras": (6, 200),
}


def _ri(r, a, b):
    return r.randint(a, b)


def condicion_al_azar(r: random.Random) -> dict:
    t = r.choice(TIPOS)
    if t in ("cruce", "comparar"):
        n1 = _ri(r, 5, 60)
        b = r.choice(["close", "serie"])
        cond = {"tipo": t, "a": r.choice(SERIES), "n": n1, "op": r.choice(["arriba", "abajo"])}
        if b == "close":
            cond["b"] = "close"
        else:
            cond["b"] = r.choice(SERIES)
            cond["n2"] = _ri(r, n1 + 5, 200)
        return cond
    if t == "rsi":
        return {"tipo": t, "n": _ri(r, 5, 30), "op": r.choice(["<", ">"]), "x": _ri(r, 15, 85)}
    if t == "adx":
        return {"tipo": t, "n": _ri(r, 7, 30), "x": _ri(r, 15, 40)}
    if t == "ruptura":
        return {"tipo": t, "n": _ri(r, 10, 100), "op": r.choice(["arriba", "abajo"])}
    if t == "volumen":
        return {"tipo": t, "n": _ri(r, 10, 50), "x": round(r.uniform(0.8, 3.0), 2)}
    if t == "bollinger":
        return {"tipo": t, "n": _ri(r, 10, 50), "k": round(r.uniform(1.5, 3.0), 2),
                "op": r.choice(["sobre_sup", "bajo_inf", "sobre_media", "bajo_media"])}
    if t == "macd":
        return {"tipo": t, "op": r.choice(["positivo", "negativo", "cruza_arriba", "cruza_abajo"])}
    if t == "esto":
        return {"tipo": t, "n": _ri(r, 5, 30), "op": r.choice(["<", ">"]), "x": _ri(r, 10, 90)}
    return {"tipo": "cci", "n": _ri(r, 10, 40), "op": r.choice(["<", ">"]), "x": _ri(r, -200, 200)}


def al_azar(r: random.Random, max_cond: int = 3) -> dict:
    sl = round(r.uniform(0.8, 4.0), 2)
    return {
        "lado": r.choice(["long", "short"]),
        "condiciones": [condicion_al_azar(r) for _ in range(r.randint(1, max_cond))],
        "sl_atr": sl,
        "tp_atr": round(r.uniform(0.8, 8.0), 2),
        "max_barras": r.randint(6, 200),
        "atr_n": 14,
    }


def id_de(e: dict) -> str:
    return hashlib.sha1(json.dumps(e, sort_keys=True).encode()).hexdigest()[:10]


def _cruce(a, b, arriba: bool):
    pa, pb = np.r_[np.nan, a[:-1]], np.r_[np.nan, b[:-1]]
    if arriba:
        return (pa <= pb) & (a > b)
    return (pa >= pb) & (a < b)


def _serie(cache: Cache, nombre: str, n: int | None):
    return cache.get(("close",)) if nombre == "close" else cache.get((nombre, n))


def evaluar_condicion(c: dict, cache: Cache) -> np.ndarray:
    t = c["tipo"]
    close = cache.get(("close",))
    with np.errstate(invalid="ignore"):
        if t in ("cruce", "comparar"):
            a = _serie(cache, c["a"], c["n"])
            b = _serie(cache, c["b"], c.get("n2"))
            arriba = c["op"] == "arriba"
            if t == "cruce":
                return _cruce(a, b, arriba)
            return a > b if arriba else a < b
        if t == "rsi":
            v = cache.get(("rsi", c["n"]))
            return v < c["x"] if c["op"] == "<" else v > c["x"]
        if t == "adx":
            return cache.get(("adx", c["n"])) > c["x"]
        if t == "ruptura":
            if c["op"] == "arriba":
                return close > cache.get(("max", c["n"]))
            return close < cache.get(("min", c["n"]))
        if t == "volumen":
            return cache.get(("volrel", c["n"])) > c["x"]
        if t == "bollinger":
            u, m, l = cache.get(("bb", c["n"], c["k"]))
            return {"sobre_sup": close > u, "bajo_inf": close < l,
                    "sobre_media": close > m, "bajo_media": close < m}[c["op"]]
        if t == "macd":
            h = cache.get(("macd",))
            z = np.zeros_like(h)
            return {"positivo": h > 0, "negativo": h < 0,
                    "cruza_arriba": _cruce(h, z, True), "cruza_abajo": _cruce(h, z, False)}[c["op"]]
        if t == "esto":
            v = cache.get(("esto", c["n"]))
            return v < c["x"] if c["op"] == "<" else v > c["x"]
        if t == "cci":
            v = cache.get(("cci", c["n"]))
            return v < c["x"] if c["op"] == "<" else v > c["x"]
    raise ValueError(t)


def senal(e: dict, cache: Cache) -> np.ndarray:
    s = np.ones(len(cache.df), dtype=bool)
    for c in e["condiciones"]:
        s &= np.nan_to_num(evaluar_condicion(c, cache), nan=0).astype(bool)
    return s


# ---------- explicación en español simple ----------

def _txt_serie(nombre, n):
    return "el precio" if nombre == "close" else f"la media {nombre.upper()} de {n} velas"


def explicar_condicion(c: dict) -> str:
    t = c["tipo"]
    if t == "cruce":
        if c["b"] == "close":  # se explica desde el precio, que es más fácil de entender
            dir_ = "abajo" if c["op"] == "arriba" else "arriba"
            return f"el precio cruza hacia {dir_} {_txt_serie(c['a'], c['n'])}"
        return (f"{_txt_serie(c['a'], c['n'])} cruza hacia {c['op']} "
                f"{_txt_serie(c['b'], c.get('n2'))}")
    if t == "comparar":
        rel = "está por encima de" if c["op"] == "arriba" else "está por debajo de"
        return f"{_txt_serie(c['a'], c['n'])} {rel} {_txt_serie(c['b'], c.get('n2'))}"
    if t == "rsi":
        return f"el RSI({c['n']}) está {'por debajo' if c['op'] == '<' else 'por encima'} de {c['x']}"
    if t == "adx":
        return f"hay tendencia fuerte (ADX({c['n']}) mayor a {c['x']})"
    if t == "ruptura":
        return (f"el precio rompe el máximo de las últimas {c['n']} velas" if c["op"] == "arriba"
                else f"el precio rompe el mínimo de las últimas {c['n']} velas")
    if t == "volumen":
        return f"el volumen es {c['x']} veces mayor que su promedio de {c['n']} velas"
    if t == "bollinger":
        d = {"sobre_sup": "cierra arriba de la banda superior", "bajo_inf": "cierra abajo de la banda inferior",
             "sobre_media": "cierra arriba de la línea del medio", "bajo_media": "cierra abajo de la línea del medio"}
        return f"el precio {d[c['op']]} de Bollinger({c['n']}, {c['k']})"
    if t == "macd":
        d = {"positivo": "es positivo", "negativo": "es negativo",
             "cruza_arriba": "pasa de negativo a positivo", "cruza_abajo": "pasa de positivo a negativo"}
        return f"el MACD {d[c['op']]}"
    if t == "esto":
        return f"el estocástico({c['n']}) está {'por debajo' if c['op'] == '<' else 'por encima'} de {c['x']}"
    return f"el CCI({c['n']}) está {'por debajo' if c['op'] == '<' else 'por encima'} de {c['x']}"


def explicar(e: dict) -> str:
    accion = "COMPRA (apuesta a que sube)" if e["lado"] == "long" else "VENDE (apuesta a que baja)"
    conds = " Y ".join(explicar_condicion(c) for c in e["condiciones"])
    return (f"{accion} cuando {conds}. "
            f"Stop-loss a {e['sl_atr']} ATR, toma ganancia a {e['tp_atr']} ATR, "
            f"y cierra sí o sí después de {e['max_barras']} velas.")


def cantidad_parametros(e: dict) -> int:
    return 3 + sum(len([v for v in c.values() if isinstance(v, (int, float))]) for c in e["condiciones"])
