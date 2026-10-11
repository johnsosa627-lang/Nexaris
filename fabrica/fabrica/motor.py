"""Motor de pruebas (backtest) con comisiones, slippage y funding.

Reglas de simulación (conservadoras, sin mirar el futuro):
- Las señales se calculan al CIERRE de una vela y se ejecutan en la APERTURA de la siguiente
  (o `retraso` velas más tarde, para probar "entrar una vela tarde").
- Toda operación lleva stop-loss. Sin stop no se opera.
- Si en una misma vela se tocan el stop y el take-profit, se asume que primero tocó el stop.
- Si el precio abre más allá del stop (hueco), se cierra al precio de apertura, no al del stop.
- Tamaño: se arriesga `riesgo_pct` del capital hasta el stop, con tope de apalancamiento.
- Slippage en cada entrada y salida (más un extra en los stops), comisión en cada lado, funding cada 8 h según la historia real.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .indicadores import atr as calcular_atr
from .metricas import calcular_metricas

try:
    from numba import njit
except ImportError:  # sin numba funciona igual, solo que más lento
    def njit(*args, **kwargs):
        if args and callable(args[0]):
            return args[0]
        return lambda f: f

MOTIVOS = {1: "stop-loss", 2: "take-profit", 3: "stop móvil", 4: "señal de salida", 5: "tiempo", 6: "fin de datos"}
TIPOS = {"pct": 0, "atr": 1, "ninguno": 2}


@dataclass(frozen=True)
class Salidas:
    stop_tipo: str = "atr"     # "pct" (% del precio) o "atr" (múltiplos de ATR)
    stop: float = 2.0
    tp_tipo: str = "atr"       # "pct", "atr" o "ninguno"
    tp: float = 4.0
    trailing: float = 0.0      # stop móvil, mismo tipo que el stop (0 = sin stop móvil)
    max_velas: int = 0         # salida por tiempo (0 = sin límite)

    def validar(self):
        if self.stop_tipo not in ("pct", "atr") or not self.stop or self.stop <= 0:
            raise ValueError("Toda operación necesita stop-loss: stop_tipo 'pct' o 'atr' y stop > 0")
        if self.tp_tipo not in TIPOS:
            raise ValueError(f"tp_tipo inválido: {self.tp_tipo}")


@dataclass(frozen=True)
class Costos:
    comision_pct: float = 0.05
    slippage_pct: float = 0.02
    usar_funding: bool = True
    # Extra en los stops: cuando el precio atraviesa el stop, la orden a mercado se llena algo peor
    slippage_stop_pct: float = 0.03

    @classmethod
    def desde_config(cls, cfg: dict) -> "Costos":
        c = cfg["costos"]
        return cls(float(c["comision_pct"]), float(c["slippage_pct"]), bool(c["usar_funding"]),
                   float(c.get("slippage_stop_pct", 0.03)))


@njit(cache=True)
def _cerrar(precio, lado, entrada, dist, nocional, fund_u, comision, slippage):
    salida = precio * (1.0 - slippage * lado)
    pnl_u = lado * (salida - entrada) - comision * (entrada + salida) - fund_u
    return salida, nocional * pnl_u / entrada, pnl_u / dist


@njit(cache=True)
def _nucleo(apertura, maximo, minimo, cierre, atr, ent_long, ent_short, sal_long, sal_short, funding,
            stop_tipo, stop_val, tp_tipo, tp_val, trail_val, max_velas, comision, slippage, retraso,
            riesgo, apal_max, slip_stop):
    n = len(cierre)
    cap = n // 2 + 2
    t_ent = np.empty(cap, np.int64)
    t_sal = np.empty(cap, np.int64)
    t_lado = np.empty(cap, np.int64)
    t_pe = np.empty(cap)
    t_ps = np.empty(cap)
    t_ret = np.empty(cap)
    t_r = np.empty(cap)
    t_mot = np.empty(cap, np.int64)
    t_fund = np.empty(cap)
    t_noc = np.empty(cap)
    k = 0

    pos = 0
    entrada = 0.0
    stop = 0.0
    tp = 0.0
    dist = 0.0
    trail_d = 0.0
    nocional = 0.0
    fund_u = 0.0
    idx_ent = 0
    movido = False
    salida_pend = False
    pend_lado = 0
    pend_idx = -1
    pend_atr = 0.0

    for i in range(n):
        # 1) entrada pendiente: se ejecuta en la apertura de esta vela
        if pend_lado != 0 and i == pend_idx:
            lado = pend_lado
            pend_lado = 0
            if pos == 0:
                pe = apertura[i] * (1.0 + slippage * lado)
                d = pe * stop_val / 100.0 if stop_tipo == 0 else pend_atr * stop_val
                if d > 0.0 and not np.isnan(d):
                    pos = lado
                    entrada = pe
                    dist = d
                    stop = pe - lado * d
                    if tp_tipo == 0:
                        tp = pe + lado * pe * tp_val / 100.0
                    elif tp_tipo == 1:
                        tp = pe + lado * pend_atr * tp_val
                    if trail_val > 0.0:
                        trail_d = pe * trail_val / 100.0 if stop_tipo == 0 else pend_atr * trail_val
                    else:
                        trail_d = 0.0
                    nocional = min(riesgo / (d / pe), apal_max)
                    idx_ent = i
                    fund_u = 0.0
                    movido = False
                    salida_pend = False

        # 2) salida por señal (decidida al cierre de la vela anterior)
        if pos != 0 and salida_pend:
            ps, ret, r = _cerrar(apertura[i], pos, entrada, dist, nocional, fund_u, comision, slippage)
            t_ent[k] = idx_ent; t_sal[k] = i; t_lado[k] = pos; t_pe[k] = entrada; t_ps[k] = ps
            t_ret[k] = ret; t_r[k] = r; t_mot[k] = 4; t_fund[k] = fund_u; t_noc[k] = nocional
            k += 1
            pos = 0
            salida_pend = False

        # 3) funding, stop y take-profit dentro de la vela
        if pos != 0:
            if funding[i] != 0.0:
                fund_u += pos * funding[i] * apertura[i]
            precio = 0.0
            mot = 0
            mot_stop = 3 if movido else 1
            if pos == 1:
                if apertura[i] <= stop:
                    precio = apertura[i]; mot = mot_stop
                elif minimo[i] <= stop:
                    precio = stop * (1.0 - slip_stop); mot = mot_stop
                elif tp_tipo != 2 and apertura[i] >= tp:
                    precio = apertura[i]; mot = 2
                elif tp_tipo != 2 and maximo[i] >= tp:
                    precio = tp; mot = 2
            else:
                if apertura[i] >= stop:
                    precio = apertura[i]; mot = mot_stop
                elif maximo[i] >= stop:
                    precio = stop * (1.0 + slip_stop); mot = mot_stop
                elif tp_tipo != 2 and apertura[i] <= tp:
                    precio = apertura[i]; mot = 2
                elif tp_tipo != 2 and minimo[i] <= tp:
                    precio = tp; mot = 2
            if mot != 0:
                ps, ret, r = _cerrar(precio, pos, entrada, dist, nocional, fund_u, comision, slippage)
                t_ent[k] = idx_ent; t_sal[k] = i; t_lado[k] = pos; t_pe[k] = entrada; t_ps[k] = ps
                t_ret[k] = ret; t_r[k] = r; t_mot[k] = mot; t_fund[k] = fund_u; t_noc[k] = nocional
                k += 1
                pos = 0

        # 4) salida por tiempo, stop móvil y señal de salida (al cierre)
        if pos != 0:
            if max_velas > 0 and i - idx_ent + 1 >= max_velas:
                ps, ret, r = _cerrar(cierre[i], pos, entrada, dist, nocional, fund_u, comision, slippage)
                t_ent[k] = idx_ent; t_sal[k] = i; t_lado[k] = pos; t_pe[k] = entrada; t_ps[k] = ps
                t_ret[k] = ret; t_r[k] = r; t_mot[k] = 5; t_fund[k] = fund_u; t_noc[k] = nocional
                k += 1
                pos = 0
            else:
                if trail_d > 0.0:
                    if pos == 1:
                        nuevo = maximo[i] - trail_d
                        if nuevo > stop:
                            stop = nuevo; movido = True
                    else:
                        nuevo = minimo[i] + trail_d
                        if nuevo < stop:
                            stop = nuevo; movido = True
                if (pos == 1 and sal_long[i]) or (pos == -1 and sal_short[i]):
                    salida_pend = True

        # 5) nueva señal de entrada (al cierre): se ejecuta 1 + retraso velas después
        if pos == 0 and pend_lado == 0 and i + 1 + retraso < n:
            if ent_long[i] and not ent_short[i]:
                pend_lado = 1; pend_idx = i + 1 + retraso; pend_atr = atr[i]
            elif ent_short[i] and not ent_long[i]:
                pend_lado = -1; pend_idx = i + 1 + retraso; pend_atr = atr[i]

    if pos != 0:
        ps, ret, r = _cerrar(cierre[n - 1], pos, entrada, dist, nocional, fund_u, comision, slippage)
        t_ent[k] = idx_ent; t_sal[k] = n - 1; t_lado[k] = pos; t_pe[k] = entrada; t_ps[k] = ps
        t_ret[k] = ret; t_r[k] = r; t_mot[k] = 6; t_fund[k] = fund_u; t_noc[k] = nocional
        k += 1

    return (t_ent[:k], t_sal[:k], t_lado[:k], t_pe[:k], t_ps[:k], t_ret[:k], t_r[:k], t_mot[:k],
            t_fund[:k], t_noc[:k])


@dataclass
class Resultado:
    operaciones: pd.DataFrame
    metricas: dict


def _bool(arr, n):
    if arr is None:
        return np.zeros(n, dtype=np.bool_)
    a = np.asarray(arr, dtype=np.bool_)
    if len(a) != n:
        raise ValueError("Las señales deben tener el mismo largo que las velas")
    return a


def backtest(velas: pd.DataFrame, ent_long, ent_short, salidas: Salidas, costos: Costos = Costos(),
             riesgo_pct: float = 1.0, apalancamiento_max: float = 3.0, sal_long=None, sal_short=None,
             funding: Optional[np.ndarray] = None, retraso: int = 0, atr_periodo: int = 14,
             atr_serie: Optional[np.ndarray] = None) -> Resultado:
    """Simula una estrategia sobre `velas` (columnas ts, open, high, low, close, volume)."""
    salidas.validar()
    n = len(velas)
    o = velas["open"].to_numpy(dtype=float)
    h = velas["high"].to_numpy(dtype=float)
    lo = velas["low"].to_numpy(dtype=float)
    c = velas["close"].to_numpy(dtype=float)
    if atr_serie is None:
        atr_serie = calcular_atr(velas["high"], velas["low"], velas["close"], atr_periodo).to_numpy(dtype=float)
    fund = np.zeros(n) if (funding is None or not costos.usar_funding) else np.asarray(funding, dtype=float)

    res = _nucleo(o, h, lo, c, np.asarray(atr_serie, dtype=float), _bool(ent_long, n), _bool(ent_short, n),
                  _bool(sal_long, n), _bool(sal_short, n), fund,
                  TIPOS[salidas.stop_tipo], float(salidas.stop), TIPOS[salidas.tp_tipo], float(salidas.tp),
                  float(salidas.trailing), int(salidas.max_velas), costos.comision_pct / 100.0,
                  costos.slippage_pct / 100.0, int(retraso), riesgo_pct / 100.0, float(apalancamiento_max),
                  costos.slippage_stop_pct / 100.0)
    ent, sal, lado, pe, ps, ret, r, mot, fu, noc = res
    ts = velas["ts"].to_numpy(dtype="int64")
    ops = pd.DataFrame({
        "entrada_ts": ts[ent], "salida_ts": ts[sal], "velas": sal - ent + 1,
        "lado": np.where(lado == 1, "LONG", "SHORT"), "precio_entrada": pe, "precio_salida": ps,
        "retorno": ret, "r": r, "motivo": [MOTIVOS[int(m)] for m in mot],
        "funding_por_unidad": fu, "apalancamiento": noc,
    })
    metricas = calcular_metricas(ops, int(ts[0]) if n else 0, int(ts[-1]) if n else 0)
    return Resultado(ops, metricas)
