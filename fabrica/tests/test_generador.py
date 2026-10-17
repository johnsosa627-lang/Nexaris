import pytest
import numpy as np

from fabrica.estrategia import identificador
from fabrica.generador import Evaluador, evolucionar, fitness, mejores
from fabrica.motor import Costos
from tests.conftest import serie_mercado


def test_fitness_ordena_bien():
    base = {"operaciones": 300, "retorno_pct": 50, "profit_factor": 1.5, "ret_dd": 5, "estabilidad": 0.9}
    e1 = {"reglas": [{}]}
    e3 = {"reglas": [{}, {}, {}]}
    assert fitness(base, e1, 200) > fitness(base, e3, 200)  # más simple, mejor
    assert fitness({**base, "ret_dd": 8}, e1, 200) > fitness(base, e1, 200)
    assert fitness({**base, "operaciones": 100}, e1, 200) < fitness(base, e1, 200)
    assert fitness({**base, "retorno_pct": -5, "profit_factor": 0.8}, e1, 200) < 0
    assert fitness({**base, "operaciones": 5}, e1, 200) == -2


def test_evolucion_reproducible_y_sin_repetidas():
    ev = Evaluador(serie_mercado(4000, 1, 0.1), None, Costos())
    a = evolucionar(ev, np.random.default_rng(3), poblacion=20, generaciones=3, min_operaciones=60)
    b = evolucionar(ev, np.random.default_rng(3), poblacion=20, generaciones=3, min_operaciones=60)
    assert list(a) == list(b)
    assert all(identificador(x["estrategia"]) == k for k, x in a.items())
    assert len(a) >= 60


def test_evolucion_mejora_sobre_el_azar_puro():
    """Con tendencias reales escondidas, el algoritmo genético encuentra algo mejor que la primera generación."""
    ev = Evaluador(serie_mercado(6000, 2, 0.12), None, Costos())
    rng = np.random.default_rng(5)
    solo_azar = evolucionar(ev, rng, poblacion=30, generaciones=0, min_operaciones=80)
    evolucionado = evolucionar(ev, np.random.default_rng(5), poblacion=30, generaciones=6, min_operaciones=80)
    assert mejores(evolucionado, 1)[0]["fitness"] >= mejores(solo_azar, 1)[0]["fitness"]
    assert mejores(evolucionado, 1)[0]["fitness"] > 1


def test_evaluador_rango_y_retraso():
    v = serie_mercado(3000, 3, 0.1)
    ev = Evaluador(v, None, Costos())
    e = {"lado": "ambos", "reglas": [{"tipo": "cruce_medias", "media": "ema", "rapida": 10, "lenta": 50}],
         "salidas": {"stop_tipo": "atr", "stop": 2.0, "tp_tipo": "atr", "tp": 4.0, "trailing": 0.0, "max_velas": 0}}
    todo = ev.correr(e).operaciones
    parte = ev.correr(e, desde=1500).operaciones
    assert parte["entrada_ts"].min() >= v["ts"].iloc[1500]
    tarde = ev.correr(e, retraso=1).operaciones
    assert len(todo) > 20 and len(tarde) > 20 and not tarde["precio_entrada"].equals(todo["precio_entrada"])


def test_fitness_prefiere_las_que_operan_seguido():
    est = {"reglas": [{"tipo": "ruptura_donchian", "n": 20}]}
    base = {"operaciones": 400, "retorno_pct": 30.0, "profit_factor": 1.5, "ret_dd": 3.0, "estabilidad": 0.8}
    lenta = fitness({**base, "operaciones_por_anio": 30}, est, 100)
    rapida = fitness({**base, "operaciones_por_anio": 200}, est, 100)
    assert rapida > lenta > 0 and rapida / lenta == pytest.approx((1 / 0.2) ** 0.5)
    assert fitness({**base, "operaciones_por_anio": 30}, est, 100, objetivo_anual=0) == rapida  # sin preferencia
