"""Chequeo estático: ningún nombre usado sin definir/importar.

Este test agarra errores como el de servicio.py (usar `EjecutorBinance` sin importarlo),
que los tests normales no ven porque esa rama solo corre al arrancar con claves reales.
"""
import subprocess
import sys
from pathlib import Path

import pytest

PAQUETE = Path(__file__).resolve().parents[1] / "fabrica"


def test_no_hay_nombres_sin_definir():
    pytest.importorskip("pyflakes")
    salida = subprocess.run([sys.executable, "-m", "pyflakes", str(PAQUETE)],
                            capture_output=True, text=True).stdout
    sin_definir = [l for l in salida.splitlines() if "undefined name" in l]
    assert not sin_definir, "Nombres usados sin definir/importar:\n" + "\n".join(sin_definir)
