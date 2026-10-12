"""Mecánica de un bot en vivo, vela por vela, con las MISMAS reglas que el motor de pruebas.

Al cerrar cada vela:
  1) se revisa la posición abierta contra esa vela (stop primero, después take-profit),
  2) salida por tiempo y actualización del stop móvil,
  3) si quedó sin posición y hay señal, entra al precio de ese momento (= apertura de la vela siguiente).
"""
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from .estrategia import Contexto, senales


def senal_ultima_vela(estrategia: dict, velas: pd.DataFrame) -> Tuple[int, float]:
    """(lado, atr) de la última vela cerrada: lado 1 = comprar, -1 = vender en corto, 0 = nada."""
    ctx = Contexto(velas)
    largo, corto = senales(ctx, estrategia)
    atr = float(ctx.ind("atr", 14).iloc[-1])
    if largo[-1] and not corto[-1]:
        return 1, atr
    if corto[-1] and not largo[-1]:
        return -1, atr
    return 0, atr


def niveles(salidas: dict, lado: int, entrada: float, atr: float) -> Optional[dict]:
    """Stop, take-profit y stop móvil a partir del precio de entrada real."""
    dist = entrada * salidas["stop"] / 100 if salidas["stop_tipo"] == "pct" else atr * salidas["stop"]
    if not dist or dist <= 0 or np.isnan(dist):
        return None
    tp = None
    if salidas["tp_tipo"] == "pct":
        tp = entrada + lado * entrada * salidas["tp"] / 100
    elif salidas["tp_tipo"] == "atr":
        tp = entrada + lado * atr * salidas["tp"]
    trail = 0.0
    if salidas.get("trailing"):
        trail = entrada * salidas["trailing"] / 100 if salidas["stop_tipo"] == "pct" else atr * salidas["trailing"]
    return {"stop": entrada - lado * dist, "tp": tp, "dist": dist, "trail": trail, "stop_movido": False}


def revisar_vela(pos: dict, vela: dict, slip_stop: float) -> Optional[Tuple[float, str]]:
    """¿La vela tocó el stop o el take-profit? Devuelve (precio bruto de salida, motivo) o None."""
    lado, stop, tp = pos["lado"], pos["stop"], pos.get("tp")
    o, h, l = vela["open"], vela["high"], vela["low"]
    motivo_stop = "stop móvil" if pos.get("stop_movido") else "stop-loss"
    if lado == 1:
        if o <= stop:
            return o, motivo_stop
        if l <= stop:
            return stop * (1 - slip_stop), motivo_stop
        if tp is not None and o >= tp:
            return o, "take-profit"
        if tp is not None and h >= tp:
            return tp, "take-profit"
    else:
        if o >= stop:
            return o, motivo_stop
        if h >= stop:
            return stop * (1 + slip_stop), motivo_stop
        if tp is not None and o <= tp:
            return o, "take-profit"
        if tp is not None and l <= tp:
            return tp, "take-profit"
    return None


def cierre_de_vela(pos: dict, vela: dict, max_velas: int) -> Optional[str]:
    """Cuenta la vela, aplica salida por tiempo y mueve el stop móvil. Devuelve 'tiempo' si hay que salir."""
    pos["velas"] = pos.get("velas", 0) + 1
    if max_velas and pos["velas"] >= max_velas:
        return "tiempo"
    if pos.get("trail"):
        if pos["lado"] == 1:
            nuevo = vela["high"] - pos["trail"]
            if nuevo > pos["stop"]:
                pos["stop"], pos["stop_movido"] = nuevo, True
        else:
            nuevo = vela["low"] + pos["trail"]
            if nuevo < pos["stop"]:
                pos["stop"], pos["stop_movido"] = nuevo, True
    return None


def resultado(pos: dict, precio_bruto: float, comision: float, slippage: float, riesgo_frac: float) -> dict:
    """Resultado de cerrar `pos` al `precio_bruto` (aplica slippage y comisiones como el backtest)."""
    lado = pos["lado"]
    salida = precio_bruto * (1 - slippage * lado)
    pnl_u = lado * (salida - pos["entrada"]) - comision * (pos["entrada"] + salida)
    r = pnl_u / pos["dist"]
    cantidad = pos.get("cantidad")
    return {"salida": salida, "r": r, "retorno": r * riesgo_frac,
            "pnl_usdt": pnl_u * cantidad if cantidad else r * pos.get("riesgo_usdt", 0.0)}
