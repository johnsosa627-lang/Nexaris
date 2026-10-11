"""Descarga y guarda velas + funding de Binance Futures (datos públicos, no requiere claves).

Uso:
    python -m fabrica.datos actualizar     # baja lo que falta (la primera vez, toda la historia)
    python -m fabrica.datos revisar        # controla huecos y errores en lo guardado
"""
import argparse
import logging
import os
import time
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger("fabrica")

COLUMNAS = ["ts", "open", "high", "low", "close", "volume"]
_MS = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}


def tf_ms(tf: str) -> int:
    return int(tf[:-1]) * _MS[tf[-1]]


def _id(simbolo: str) -> str:
    return simbolo.split(":")[0].replace("/", "")


def ruta_velas(carpeta: str, simbolo: str, tf: str) -> str:
    return os.path.join(carpeta, "velas", f"{_id(simbolo)}_{tf}.csv.gz")


def ruta_funding(carpeta: str, simbolo: str) -> str:
    return os.path.join(carpeta, "funding", f"{_id(simbolo)}.csv.gz")


def crear_cliente():
    import ccxt
    return ccxt.binanceusdm({"enableRateLimit": True})


def _reintentar(funcion, *args, intentos=5, **kwargs):
    for i in range(intentos):
        try:
            return funcion(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 - errores de red: esperar y reintentar
            if i == intentos - 1:
                raise
            espera = 2 ** (i + 1)
            log.warning("Error de red (%s). Reintento en %ss", e, espera)
            time.sleep(espera)


# ------------------------------------------------------------------ descarga
def descargar_velas(cliente, simbolo: str, tf: str, desde_ms: int, ahora_ms: Optional[int] = None,
                    limite: int = 1500) -> pd.DataFrame:
    """Baja velas desde `desde_ms` hasta hoy, de a `limite` por pedido. Descarta la vela sin cerrar."""
    ahora_ms = ahora_ms or int(time.time() * 1000)
    paso = tf_ms(tf)
    filas, desde = [], desde_ms
    while desde < ahora_ms:
        lote = _reintentar(cliente.fetch_ohlcv, simbolo, tf, since=desde, limit=limite)
        if not lote:
            break
        filas.extend(lote)
        ultimo = lote[-1][0]
        if ultimo < desde:
            break
        desde = ultimo + paso
        if len(lote) < limite:
            break
    df = pd.DataFrame(filas, columns=COLUMNAS)
    if df.empty:
        return df
    df = df[df["ts"] + paso <= ahora_ms]  # solo velas cerradas
    return _limpiar(df)


def descargar_funding(cliente, simbolo: str, desde_ms: int, ahora_ms: Optional[int] = None,
                      limite: int = 1000) -> pd.DataFrame:
    ahora_ms = ahora_ms or int(time.time() * 1000)
    filas, desde = [], desde_ms
    while desde < ahora_ms:
        lote = _reintentar(cliente.fetch_funding_rate_history, simbolo, since=desde, limit=limite)
        if not lote:
            break
        filas.extend({"ts": int(x["timestamp"]), "tasa": float(x["fundingRate"])} for x in lote)
        ultimo = int(lote[-1]["timestamp"])
        if ultimo < desde or len(lote) < limite:
            break
        desde = ultimo + 1
    df = pd.DataFrame(filas, columns=["ts", "tasa"])
    return df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)


def _limpiar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ts"] = df["ts"].astype("int64")
    for c in COLUMNAS[1:]:
        df[c] = df[c].astype(float)
    return df.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)


# ------------------------------------------------------------------ guardar / cargar
def _guardar(df: pd.DataFrame, ruta: str):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    temporal = ruta + ".tmp"
    df.to_csv(temporal, index=False, compression="gzip")
    os.replace(temporal, ruta)


def _leer(ruta: str, columnas: list) -> pd.DataFrame:
    if not os.path.exists(ruta):
        return pd.DataFrame(columns=columnas)
    return pd.read_csv(ruta)


def cargar_velas(carpeta: str, simbolo: str, tf: str) -> pd.DataFrame:
    df = _leer(ruta_velas(carpeta, simbolo, tf), COLUMNAS)
    return _limpiar(df) if not df.empty else df


def cargar_funding(carpeta: str, simbolo: str) -> pd.DataFrame:
    return _leer(ruta_funding(carpeta, simbolo), ["ts", "tasa"])


def actualizar(cfg: dict, cliente=None, ahora_ms: Optional[int] = None) -> list:
    """Completa velas y funding de todos los símbolos/temporalidades. Devuelve un resumen."""
    cliente = cliente or crear_cliente()
    carpeta = cfg["datos"]["carpeta"]
    inicio = int(pd.Timestamp(cfg["datos"]["desde"], tz="UTC").timestamp() * 1000)
    resumen = []
    for simbolo in cfg["datos"]["simbolos"]:
        for tf in cfg["datos"]["temporalidades"]:
            viejo = cargar_velas(carpeta, simbolo, tf)
            desde = int(viejo["ts"].iloc[-1]) + tf_ms(tf) if not viejo.empty else inicio
            nuevo = descargar_velas(cliente, simbolo, tf, desde, ahora_ms)
            total = _limpiar(pd.concat([viejo, nuevo]) if not viejo.empty else nuevo) if not nuevo.empty else viejo
            if not nuevo.empty:
                _guardar(total, ruta_velas(carpeta, simbolo, tf))
            resumen.append({"simbolo": simbolo, "tf": tf, "nuevas": len(nuevo), "total": len(total)})
            log.info("%s %s: +%d velas (total %d)", simbolo, tf, len(nuevo), len(total))
        viejo = cargar_funding(carpeta, simbolo)
        desde = int(viejo["ts"].iloc[-1]) + 1 if not viejo.empty else inicio
        nuevo = descargar_funding(cliente, simbolo, desde, ahora_ms)
        if not nuevo.empty:
            total = pd.concat([viejo, nuevo]) if not viejo.empty else nuevo
            total = total.drop_duplicates("ts").sort_values("ts")
            _guardar(total.reset_index(drop=True), ruta_funding(carpeta, simbolo))
        resumen.append({"simbolo": simbolo, "tf": "funding", "nuevas": len(nuevo),
                        "total": len(viejo) + len(nuevo)})
    return resumen


# ------------------------------------------------------------------ preparación para el motor
def dividir_examen(df: pd.DataFrame, meses: int):
    """Separa los últimos `meses` como examen final. Devuelve (trabajo, examen, corte_ms)."""
    if df.empty:
        return df, df, None
    fin = pd.Timestamp(int(df["ts"].iloc[-1]), unit="ms", tz="UTC")
    corte = int((fin - pd.DateOffset(months=meses)).timestamp() * 1000)
    trabajo = df[df["ts"] < corte].reset_index(drop=True)
    examen = df[df["ts"] >= corte].reset_index(drop=True)
    return trabajo, examen, corte


def alinear_funding(ts_velas: np.ndarray, funding: pd.DataFrame, tf: str) -> np.ndarray:
    """Tasa de funding cobrada dentro de cada vela (0 si no hay cobro en esa vela)."""
    resultado = np.zeros(len(ts_velas))
    if funding is None or funding.empty or len(ts_velas) == 0:
        return resultado
    ts_f = funding["ts"].to_numpy(dtype="int64")
    tasas = funding["tasa"].to_numpy(dtype=float)
    idx = np.searchsorted(ts_velas, ts_f, side="right") - 1
    validos = (idx >= 0) & (ts_f < ts_velas[np.clip(idx, 0, None)] + tf_ms(tf))
    np.add.at(resultado, idx[validos], tasas[validos])
    return resultado


def revisar_calidad(df: pd.DataFrame, tf: str) -> dict:
    """Controla velas faltantes, duplicadas y precios incoherentes."""
    if df.empty:
        return {"velas": 0, "huecos": 0, "velas_faltantes": 0, "duplicadas": 0, "incoherentes": 0}
    dif = np.diff(df["ts"].to_numpy())
    paso = tf_ms(tf)
    huecos = dif[dif > paso]
    incoherentes = ((df["high"] < df[["open", "close"]].max(axis=1)) |
                    (df["low"] > df[["open", "close"]].min(axis=1)) |
                    (df[["open", "high", "low", "close"]] <= 0).any(axis=1) |
                    df[COLUMNAS].isna().any(axis=1))
    return {
        "velas": len(df),
        "desde": str(pd.Timestamp(int(df["ts"].iloc[0]), unit="ms", tz="UTC").date()),
        "hasta": str(pd.Timestamp(int(df["ts"].iloc[-1]), unit="ms", tz="UTC").date()),
        "huecos": int(len(huecos)),
        "velas_faltantes": int((huecos // paso - 1).sum()),
        "duplicadas": int((dif == 0).sum()),
        "incoherentes": int(incoherentes.sum()),
    }


def main():
    from .config import cargar_config
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    p = argparse.ArgumentParser(description="Datos de Binance Futures")
    p.add_argument("accion", choices=["actualizar", "revisar"])
    args = p.parse_args()
    cfg = cargar_config()
    if args.accion == "actualizar":
        for r in actualizar(cfg):
            print(f"{r['simbolo']:<16} {r['tf']:<8} nuevas: {r['nuevas']:>7}  total: {r['total']:>7}")
    else:
        for simbolo in cfg["datos"]["simbolos"]:
            for tf in cfg["datos"]["temporalidades"]:
                c = revisar_calidad(cargar_velas(cfg["datos"]["carpeta"], simbolo, tf), tf)
                print(f"{simbolo:<16} {tf:<4} {c}")


if __name__ == "__main__":
    main()
