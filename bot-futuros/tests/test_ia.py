from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import velas_sinteticas
from trader.estado import Estado
from trader.ia import ErrorIA, FiltroIA, parsear_respuesta, tabla_velas
from trader.indicadores import agregar_indicadores, ohlcv_a_dataframe


class Resp:
    def __init__(self, contenido=None, status=200, crudo=None):
        self.status_code = status
        self._json = crudo if crudo is not None else {"choices": [{"message": {"content": contenido}}]}
        self.text = str(self._json)

    def json(self):
        return self._json


class PostFalso:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.modelos = []

    def __call__(self, url, headers, json, timeout):
        self.modelos.append(json["model"])
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def df():
    return agregar_indicadores(ohlcv_a_dataframe(velas_sinteticas(100)))


def filtro(cfg, tmp_path, respuestas, reloj=None):
    estado = Estado(str(tmp_path / "e.json"))
    post = PostFalso(respuestas)
    reloj = reloj or (lambda: datetime(2026, 10, 12, 10, tzinfo=timezone.utc))
    return FiltroIA(cfg, estado, post=post, reloj=reloj), post, estado


@pytest.mark.parametrize("texto,score", [
    ('{"score": 75, "motivo": "tendencia"}', 75),
    ('```json\n{"score": 61, "motivo": "ok"}\n```', 61),
    ('Análisis: {"score": "40", "motivo": "débil"} fin', 40),
    ('{"score": 59.6, "motivo": "x"}', 60),
])
def test_parsear_respuesta(texto, score):
    assert parsear_respuesta(texto)[0] == score


@pytest.mark.parametrize("texto", ["", "sin json", '{"motivo": "falta score"}', '{"score": 150}'])
def test_parsear_respuesta_invalida(texto):
    with pytest.raises(ErrorIA):
        parsear_respuesta(texto)


def test_tabla_tiene_20_velas_e_indicadores(df):
    tabla = tabla_velas(df, 20).strip().splitlines()
    assert len(tabla) == 21 and "ema9" in tabla[0] and "macd_hist" in tabla[0]


def test_aprueba_con_score_60(cfg, tmp_path, df):
    f, post, _ = filtro(cfg, tmp_path, [Resp('{"score": 60, "motivo": "bien"}')])
    aprobada, score, motivo = f.evaluar(df, "LONG")
    assert aprobada and score == 60 and "bien" in motivo
    assert post.modelos == ["nex-agi/nex-n2.5-pro:free"]


def test_rechaza_score_bajo(cfg, tmp_path, df):
    f, _, _ = filtro(cfg, tmp_path, [Resp('{"score": 59, "motivo": "dudoso"}')])
    assert f.evaluar(df, "SHORT")[:2] == (False, 59)


def test_usa_modelo_de_respaldo(cfg, tmp_path, df):
    f, post, _ = filtro(cfg, tmp_path, [Resp(status=429, crudo={"error": "rate"}), Resp('{"score": 80, "motivo": "ok"}')])
    aprobada, score, _ = f.evaluar(df, "LONG")
    assert aprobada and score == 80
    assert post.modelos == ["nex-agi/nex-n2.5-pro:free", "nex-agi/nex-n2.5-mini"]
    assert f.uso()["dia"] == 2


def test_si_fallan_ambos_no_opera(cfg, tmp_path, df):
    f, _, _ = filtro(cfg, tmp_path, [TimeoutError("timeout"), Resp("no es json")])
    aprobada, score, motivo = f.evaluar(df, "LONG")
    assert not aprobada and score is None and "IA no disponible" in motivo


def test_presupuesto_diario_y_semanal(cfg, tmp_path, df):
    ahora = [datetime(2026, 10, 12, 10, tzinfo=timezone.utc)]  # lunes
    f, post, _ = filtro(cfg, tmp_path, [Resp('{"score": 70, "motivo": ""}')] * 20, reloj=lambda: ahora[0])
    for _ in range(5):
        assert f.evaluar(df, "LONG")[0]
    assert not f.presupuesto_disponible()
    aprobada, score, motivo = f.evaluar(df, "LONG")
    assert not aprobada and score is None and "agotado" in motivo
    assert len(post.modelos) == 5
    ahora[0] += timedelta(days=1)  # nuevo día: 5 más disponibles (semana 10)
    for _ in range(5):
        assert f.evaluar(df, "LONG")[0]
    ahora[0] += timedelta(days=1)  # tope semanal alcanzado
    assert not f.presupuesto_disponible()
    ahora[0] += timedelta(days=6)  # semana siguiente
    assert f.presupuesto_disponible()


def test_sin_api_key(tmp_path, df):
    from trader.config import Config
    f, post, _ = filtro(Config(openrouter_api_key=""), tmp_path, [])
    assert f.evaluar(df, "LONG") == (False, None, "Falta OPENROUTER_API_KEY")
