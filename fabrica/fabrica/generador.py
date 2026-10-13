"""Inventa estrategias: generación aleatoria + algoritmo genético (cruzar y mutar a las mejores)."""
import logging
from typing import Optional

import numpy as np
import pandas as pd

from .estrategia import Contexto, cruzar, estrategia_aleatoria, identificador, mutar, senales
from .motor import Costos, Salidas, backtest

log = logging.getLogger("fabrica")


class Evaluador:
    """Corre estrategias sobre un conjunto de velas fijo (reutiliza los indicadores)."""

    def __init__(self, velas: pd.DataFrame, funding: Optional[np.ndarray], costos: Costos,
                 riesgo_pct: float = 1.0, apalancamiento_max: float = 3.0, externos: Optional[dict] = None):
        self.velas = velas.reset_index(drop=True)
        self.externos = externos
        self.ctx = Contexto(self.velas, externos)
        self.atr = self.ctx.ind("atr", 14).to_numpy()
        self.funding = funding
        self.costos = costos
        self.riesgo_pct = riesgo_pct
        self.apal = apalancamiento_max

    def senales(self, est):
        return senales(self.ctx, est)

    def correr(self, est: dict, retraso: int = 0, desde: int = 0, hasta: Optional[int] = None,
               costos: Optional[Costos] = None, sen=None):
        """Backtest de `est` en las velas [desde, hasta). Las señales se calculan con toda la historia previa."""
        largo, corto = sen if sen is not None else self.senales(est)
        hasta = len(self.velas) if hasta is None else hasta
        sl = slice(desde, hasta)
        fund = self.funding[sl] if self.funding is not None else None
        return backtest(self.velas.iloc[sl].reset_index(drop=True), largo[sl], corto[sl],
                        Salidas(**est["salidas"]), costos or self.costos, self.riesgo_pct, self.apal,
                        funding=fund, retraso=retraso, atr_serie=self.atr[sl])


def fitness(m: dict, est: dict, min_operaciones: int) -> float:
    """Puntaje para ordenar estrategias: premia ganancia/caída y curva pareja, castiga complejidad."""
    if m["operaciones"] < max(10, min_operaciones // 4):
        return -2.0
    if m["retorno_pct"] <= 0:
        return -1.0 + min(m["profit_factor"], 1.0)
    cantidad = min(1.0, m["operaciones"] / min_operaciones)
    complejidad = 1.0 - 0.05 * (len(est["reglas"]) - 1)
    return float(min(m["ret_dd"], 50) * max(m["estabilidad"], 0.01) * cantidad * complejidad)


def evolucionar(evaluador: Evaluador, rng: np.random.Generator, poblacion: int = 150, generaciones: int = 25,
                elite_pct: float = 10, prob_cruce: float = 0.7, prob_mutacion: float = 0.4,
                max_filtros: int = 2, min_operaciones: int = 140) -> dict:
    """Devuelve el archivo de TODAS las estrategias probadas: id -> {estrategia, fitness, metricas}."""
    archivo = {}

    def evaluar(est):
        clave = identificador(est)
        if clave not in archivo:
            try:
                m = evaluador.correr(est).metricas
                archivo[clave] = {"estrategia": est, "fitness": fitness(m, est, min_operaciones), "metricas": m}
            except Exception as e:  # noqa: BLE001 - una estrategia rota no frena la fábrica
                log.debug("Estrategia descartada por error: %s", e)
                archivo[clave] = {"estrategia": est, "fitness": -3.0, "metricas": {"operaciones": 0}}
        return clave

    actuales = [evaluar(estrategia_aleatoria(rng, max_filtros)) for _ in range(poblacion)]
    n_elite = max(1, int(poblacion * elite_pct / 100))
    for gen in range(generaciones):
        orden = sorted(set(actuales), key=lambda k: archivo[k]["fitness"], reverse=True)
        nueva = orden[:n_elite]
        intentos = 0
        while len(nueva) < poblacion and intentos < poblacion * 20:
            intentos += 1
            padre = _torneo(rng, actuales, archivo)
            if rng.random() < prob_cruce:
                hija = cruzar(rng, archivo[padre]["estrategia"], archivo[_torneo(rng, actuales, archivo)]["estrategia"], max_filtros)
            else:
                hija = archivo[padre]["estrategia"]
            if rng.random() < prob_mutacion or identificador(hija) in archivo:
                hija = mutar(rng, hija, max_filtros)
            if identificador(hija) in archivo and rng.random() < 0.8:
                hija = estrategia_aleatoria(rng, max_filtros)  # sangre nueva para no estancarse
            clave = evaluar(hija)
            if clave not in nueva:
                nueva.append(clave)
        actuales = nueva
        mejor = archivo[max(actuales, key=lambda k: archivo[k]["fitness"])]
        log.debug("Generación %d: mejor fitness %.3f (%d probadas)", gen + 1, mejor["fitness"], len(archivo))
    return archivo


def _torneo(rng, actuales, archivo, k: int = 3) -> str:
    elegidos = [actuales[int(i)] for i in rng.integers(len(actuales), size=k)]
    return max(elegidos, key=lambda c: archivo[c]["fitness"])


def mejores(archivo: dict, n: int) -> list:
    return sorted(archivo.values(), key=lambda x: x["fitness"], reverse=True)[:n]
