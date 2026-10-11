import numpy as np
import pandas as pd
import pytest

from fabrica import datos
from tests.conftest import H, T0


class ClienteFalso:
    """Binance simulado: velas de 1h y funding cada 8h desde T0."""

    def __init__(self, fin_ms, saltear=()):
        self.fin = fin_ms
        self.saltear = set(saltear)
        self.pedidos = 0

    def fetch_ohlcv(self, simbolo, tf, since, limit):
        self.pedidos += 1
        paso = datos.tf_ms(tf)
        inicio = max(since, T0)
        inicio += (-(inicio - T0)) % paso
        filas = []
        ts = inicio
        while ts < self.fin and len(filas) < limit:
            if ts not in self.saltear:
                p = 100 + (ts - T0) / paso * 0.01
                filas.append([ts, p, p + 1, p - 1, p + 0.5, 10.0])
            ts += paso
        return filas

    def fetch_funding_rate_history(self, simbolo, since, limit):
        ts = max(since, T0)
        ts += (-(ts - T0)) % (8 * H)
        out = []
        while ts < self.fin and len(out) < limit:
            out.append({"timestamp": ts, "fundingRate": 0.0001})
            ts += 8 * H
        return out


def cfg(tmp_path):
    return {"datos": {"carpeta": str(tmp_path), "simbolos": ["XRP/USDT:USDT"], "temporalidades": ["1h", "4h"],
                      "desde": "2021-01-01", "meses_examen": 6}}


def test_descarga_paginada_y_sin_vela_abierta():
    fin = T0 + 4000 * H + 30 * 60_000  # media hora dentro de una vela abierta
    cli = ClienteFalso(fin)
    df = datos.descargar_velas(cli, "XRP/USDT:USDT", "1h", T0, ahora_ms=fin, limite=1500)
    assert len(df) == 4000 and cli.pedidos == 3
    assert df["ts"].is_monotonic_increasing and df["ts"].is_unique
    assert df["ts"].iloc[-1] + H <= fin


def test_actualizar_incremental(tmp_path):
    c = cfg(tmp_path)
    fin = T0 + 1000 * H
    r = datos.actualizar(c, ClienteFalso(fin), ahora_ms=fin)
    assert {x["tf"]: x["nuevas"] for x in r} == {"1h": 1000, "4h": 250, "funding": 125}
    fin2 = fin + 100 * H
    cli = ClienteFalso(fin2)
    r = datos.actualizar(c, cli, ahora_ms=fin2)
    assert {x["tf"]: (x["nuevas"], x["total"]) for x in r} == {"1h": (100, 1100), "4h": (25, 275), "funding": (13, 138)}
    df = datos.cargar_velas(str(tmp_path), "XRP/USDT:USDT", "1h")
    assert len(df) == 1100 and df["ts"].is_unique
    r = datos.actualizar(c, ClienteFalso(fin2), ahora_ms=fin2)  # sin novedades
    assert all(x["nuevas"] == 0 for x in r)


def test_dividir_examen():
    ts = pd.date_range("2021-01-01", "2023-12-31 23:00", freq="h", tz="UTC")
    df = pd.DataFrame({"ts": ts.as_unit("ms").asi8})
    trabajo, examen, corte = datos.dividir_examen(df, 6)
    assert pd.Timestamp(corte, unit="ms", tz="UTC") == pd.Timestamp("2023-06-30 23:00", tz="UTC")
    assert trabajo["ts"].max() < corte <= examen["ts"].min()
    assert len(trabajo) + len(examen) == len(df)


def test_alinear_funding():
    ts = T0 + np.arange(24, dtype="int64") * H
    f = pd.DataFrame({"ts": [T0, T0 + 8 * H, T0 + 16 * H + 5], "tasa": [0.0001, -0.0002, 0.0003]})
    a = datos.alinear_funding(ts, f, "1h")
    assert a[0] == 0.0001 and a[8] == -0.0002 and a[16] == 0.0003 and np.count_nonzero(a) == 3
    ts4 = T0 + np.arange(6, dtype="int64") * 4 * H
    a4 = datos.alinear_funding(ts4, f, "4h")
    assert list(a4[:5]) == [0.0001, 0, -0.0002, 0, 0.0003]


def test_revisar_calidad_detecta_huecos():
    fin = T0 + 100 * H
    df = datos.descargar_velas(ClienteFalso(fin, saltear={T0 + 10 * H, T0 + 11 * H, T0 + 50 * H}), "X", "1h", T0, fin)
    c = datos.revisar_calidad(df, "1h")
    assert c["velas"] == 97 and c["huecos"] == 2 and c["velas_faltantes"] == 3 and c["incoherentes"] == 0
    df.loc[5, "high"] = 0.5
    assert datos.revisar_calidad(df, "1h")["incoherentes"] == 1
