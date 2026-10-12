"""Lee config.yaml. La carpeta de datos se puede cambiar con la variable FABRICA_DATOS."""
import os
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]


def cargar_config(ruta: str = None) -> dict:
    ruta = Path(ruta or os.getenv("FABRICA_CONFIG") or RAIZ / "config.yaml")
    with open(ruta, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    carpeta = os.getenv("FABRICA_DATOS") or cfg["datos"]["carpeta"]
    if not os.path.isabs(carpeta):
        carpeta = str(RAIZ / carpeta)
    cfg["datos"]["carpeta"] = carpeta
    salida = os.getenv("FABRICA_RESULTADOS") or cfg.get("salida", {}).get("carpeta", "resultados")
    if not os.path.isabs(salida):
        salida = str(RAIZ / salida)
    cfg.setdefault("salida", {})["carpeta"] = salida
    return cfg
