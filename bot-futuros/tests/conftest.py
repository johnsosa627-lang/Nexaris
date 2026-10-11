import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trader.config import Config  # noqa: E402
from trader.estrategia import evaluar_senal  # noqa: E402
from trader.indicadores import agregar_indicadores, ohlcv_a_dataframe  # noqa: E402

TF_MS = 15 * 60_000
T0 = 1_760_000_000_000 - (1_760_000_000_000 % TF_MS)


def velas_sinteticas(n=300, semilla=0, precio=0.5, vol=0.004):
    """Random walk con volumen aleatorio: [ts, o, h, l, c, v]."""
    rng = np.random.default_rng(semilla)
    velas = []
    cierre = precio
    for i in range(n):
        apertura = cierre
        cierre = max(0.01, apertura * math.exp(rng.normal(0, vol)))
        alto = max(apertura, cierre) * (1 + abs(rng.normal(0, vol / 3)))
        bajo = min(apertura, cierre) * (1 - abs(rng.normal(0, vol / 3)))
        volumen = float(rng.lognormal(10, 0.5))
        velas.append([T0 + i * TF_MS, apertura, alto, bajo, cierre, volumen])
    return velas


def buscar_senal(lado, n=300):
    """Devuelve (velas, indice) donde la vela `indice` genera la señal pedida."""
    for semilla in range(500):
        velas = velas_sinteticas(n, semilla)
        df = agregar_indicadores(ohlcv_a_dataframe(velas))
        for i in range(100, n):
            if evaluar_senal(df.iloc[: i + 1]) == lado:
                return velas, i
    raise AssertionError(f"No se encontró señal {lado}")


@pytest.fixture
def cfg(tmp_path):
    return Config(modo="papel", data_dir=str(tmp_path), openrouter_api_key="x",
                  ia_max_dia=5, ia_max_semana=10)
