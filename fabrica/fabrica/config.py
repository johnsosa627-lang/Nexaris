"""Carga config.yaml y variables de entorno."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", RAIZ / "data"))


def cargar(ruta: str | os.PathLike | None = None) -> dict:
    ruta = Path(ruta or os.environ.get("FABRICA_CONFIG", RAIZ / "config.yaml"))
    with open(ruta, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["telegram"] = {
        "token": os.environ.get("TELEGRAM_TOKEN", ""),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
    }
    # Plata real: solo si las DOS llaves están puestas. Esta versión no opera en real todavía.
    cfg["live"] = os.environ.get("LIVE_TRADING", "false").lower() == "true"
    return cfg


def costo_ida_vuelta(cfg: dict) -> float:
    c = cfg["costos"]
    return 2 * (c["comision_lado"] + c["slippage_lado"])
