"""Motor de pruebas (backtest).

Reglas para que sea realista:
- La señal se calcula con la vela YA CERRADA y se entra en la apertura de la siguiente.
- Si en una misma vela se tocan el stop y la toma de ganancia, se asume lo peor (el stop).
- Si el precio abre más allá del stop (hueco), se sale al precio de apertura (peor que el stop).
- Comisiones, slippage y funding se descuentan en cada operación.
- Una sola operación abierta a la vez por estrategia.
Los resultados se miden en "R": 1R = lo que se arriesga por operación (1 % del capital).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .datos import TF_MS
from .estrategia import senal
from .indicadores import Cache


@dataclass
class Resultado:
    r: np.ndarray          # resultado de cada operación en R
    entradas: np.ndarray   # índice de vela de entrada
    salidas: np.ndarray    # índice de vela de salida
    ts_salida: np.ndarray  # timestamp (ms) de salida
    costo_r: np.ndarray    # cuánto costó cada operación (comisiones+slippage+funding) en R


VACIO = Resultado(np.array([]), np.array([], int), np.array([], int), np.array([], np.int64), np.array([]))


def correr(e: dict, cache: Cache, ini: int = 0, fin: int | None = None, *, costo_rt: float = 0.0012,
           funding_8h: float = 0.0001, tf: str = "1h", retraso: int = 0, mult_costo: float = 1.0,
           sig: np.ndarray | None = None) -> Resultado:
    df = cache.df
    n = len(df)
    fin = n if fin is None else min(fin, n)
    o = df["open"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    ts = df["ts"].to_numpy()
    a = cache.get(("atr", e.get("atr_n", 14)))
    s = senal(e, cache) if sig is None else sig
    idx = np.flatnonzero(s[ini:fin]) + ini
    largo = e["lado"] == "long"
    horas_barra = TF_MS[tf] / 3_600_000
    costo = costo_rt * mult_costo
    mb = int(e["max_barras"])
    rs, ents, sals, tss, cst = [], [], [], [], []
    libre_desde = ini
    for i in idx:
        if i < libre_desde:
            continue
        ent_i = i + 1 + retraso
        if ent_i >= fin or not np.isfinite(a[i]) or a[i] <= 0:
            continue
        entrada = o[ent_i]
        dist = e["sl_atr"] * a[i]
        if dist <= 0 or dist >= entrada * 0.5:
            continue
        if largo:
            sl, tp = entrada - dist, entrada + e["tp_atr"] * a[i]
        else:
            sl, tp = entrada + dist, entrada - e["tp_atr"] * a[i]
        ult = min(ent_i + mb, fin) - 1
        hh, ll = h[ent_i:ult + 1], l[ent_i:ult + 1]
        if largo:
            golpe_sl = np.flatnonzero(ll <= sl)
            golpe_tp = np.flatnonzero(hh >= tp)
        else:
            golpe_sl = np.flatnonzero(hh >= sl)
            golpe_tp = np.flatnonzero(ll <= tp)
        k_sl = golpe_sl[0] if len(golpe_sl) else 10**9
        k_tp = golpe_tp[0] if len(golpe_tp) else 10**9
        if k_sl == 10**9 and k_tp == 10**9:
            sal_i, precio = ult, c[ult]
        elif k_sl <= k_tp:  # en empate, gana el stop (lo peor)
            sal_i = ent_i + k_sl
            op = o[sal_i]
            precio = min(sl, op) if largo else max(sl, op)
        else:
            sal_i = ent_i + k_tp
            op = o[sal_i]
            precio = max(tp, op) if largo else min(tp, op)
        bruto = (precio - entrada) if largo else (entrada - precio)
        barras = sal_i - ent_i + 1
        gastos = entrada * (costo + funding_8h * barras * horas_barra / 8)
        rs.append((bruto - gastos) / dist)
        cst.append(gastos / dist)
        ents.append(ent_i)
        sals.append(sal_i)
        tss.append(ts[sal_i])
        libre_desde = sal_i + 1
    if not rs:
        return VACIO
    return Resultado(np.array(rs), np.array(ents), np.array(sals), np.array(tss, dtype=np.int64), np.array(cst))
