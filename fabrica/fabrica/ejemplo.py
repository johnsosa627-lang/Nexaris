"""Prueba el motor con una estrategia de ejemplo sobre datos ya descargados.

    python -m fabrica.ejemplo --simbolo XRP/USDT:USDT --tf 1h

Estrategia de ejemplo (solo para ver que el motor funciona, NO es una recomendación):
compra cuando la EMA 20 cruza arriba de la EMA 50, vende en corto cuando cruza abajo;
stop-loss a 2 ATR y take-profit a 4 ATR. Usa solo la parte de "trabajo" (nunca el examen final).
"""
import argparse

from .config import cargar_config
from .datos import alinear_funding, cargar_funding, cargar_velas, dividir_examen
from .indicadores import ema
from .metricas import explicar
from .motor import Costos, Salidas, backtest


def senales_cruce_ema(velas, rapida=20, lenta=50):
    r, l = ema(velas["close"], rapida), ema(velas["close"], lenta)
    arriba = r > l
    cruce_arriba = arriba & ~arriba.shift(1, fill_value=False) & l.notna() & l.shift(1).notna()
    abajo = r < l
    cruce_abajo = abajo & ~abajo.shift(1, fill_value=False) & l.notna() & l.shift(1).notna()
    return cruce_arriba.to_numpy(), cruce_abajo.to_numpy()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--simbolo", default="XRP/USDT:USDT")
    p.add_argument("--tf", default="1h")
    args = p.parse_args()
    cfg = cargar_config()
    velas = cargar_velas(cfg["datos"]["carpeta"], args.simbolo, args.tf)
    if velas.empty:
        raise SystemExit("No hay datos. Corré primero: python -m fabrica.datos actualizar")
    trabajo, examen, corte = dividir_examen(velas, cfg["datos"]["meses_examen"])
    funding = alinear_funding(trabajo["ts"].to_numpy(), cargar_funding(cfg["datos"]["carpeta"], args.simbolo), args.tf)
    largo, corto = senales_cruce_ema(trabajo)
    res = backtest(trabajo, largo, corto, Salidas("atr", 2, "atr", 4), Costos.desde_config(cfg),
                   riesgo_pct=cfg["riesgo"]["riesgo_por_operacion_pct"],
                   apalancamiento_max=cfg["riesgo"]["apalancamiento_max"], funding=funding)
    print(f"{args.simbolo} {args.tf} — {len(trabajo)} velas de trabajo ({len(examen)} guardadas para el examen final)\n")
    print(explicar(res.metricas, cfg["riesgo"]["capital_inicial"]))


if __name__ == "__main__":
    main()
