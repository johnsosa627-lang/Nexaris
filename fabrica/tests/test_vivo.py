"""Liga y bots en vivo: mismas reglas que el backtest, protección de la cuenta, ascensos y jubilaciones."""
import os

import numpy as np
import pandas as pd
import pytest

from fabrica.config import cargar_config
from fabrica.generador import Evaluador
from fabrica.liga import Liga
from fabrica.motor import Costos
from tests.conftest import H, serie_mercado

TENDENCIA = {"lado": "ambos", "reglas": [{"tipo": "ruptura_donchian", "n": 20}],
             "salidas": {"stop_tipo": "atr", "stop": 2.0, "tp_tipo": "atr", "tp": 4.0, "trailing": 3.0, "max_velas": 60}}


class MercadoFalso:
    def __init__(self, series=None, minimo=(0.1, 5.0)):
        self.series = series or {}
        self.minimo = minimo
        self.ultimo = {}

    def velas(self, simbolo, tf, limite, ahora_ms):
        df = self.series[(simbolo, tf)]
        return df[df["ts"] + H <= ahora_ms].tail(limite).reset_index(drop=True)

    def precio(self, simbolo):
        return self.ultimo.get(simbolo, 100.0)

    def limites(self, simbolo):
        return self.minimo

    def ajustar(self, simbolo, q):
        return float(np.floor(q * 10) / 10)


def cfg_prueba(capital=15, **liga):
    cfg = cargar_config()
    cfg["liga"].update(liga)
    cfg["riesgo"]["capital_inicial"] = capital  # los casos de prueba están pensados con 15 USDT
    return cfg


def registro(i, simbolo="AAA/USDT:USDT", estrategia=TENDENCIA, diario=None, fitness=10.0, mc_dd=15.0, r_bt=None):
    return {"id": f"bot{i}", "simbolo": simbolo, "tf": "1h", "estrategia": estrategia, "explicacion": "prueba",
            "fitness": fitness, "montecarlo": {"drawdown_p95_pct": mc_dd},
            "r_backtest": r_bt if r_bt is not None else list(np.random.default_rng(i).normal(0.3, 2, 300)),
            "retornos_diarios": diario if diario is not None else {}}


def liga_papel(tmp_path, cfg=None, reloj=None, mercado=None):
    mensajes = []
    t = {"ahora": 1_700_000_000.0}
    liga = Liga(cfg or cfg_prueba(), str(tmp_path), mercado or MercadoFalso(), None, mensajes.append,
                reloj=reloj or (lambda: t["ahora"]), modo="papel")
    return liga, mensajes, t


# ------------------------------------------------------------------ mismas reglas que el backtest
def test_suplente_en_vivo_hace_lo_mismo_que_el_backtest(tmp_path):
    v = serie_mercado(1200, 4, 0.2)
    ops_bt = Evaluador(v, None, Costos(usar_funding=False)).correr(TENDENCIA).operaciones
    ops_bt = ops_bt[ops_bt["motivo"] != "fin de datos"]
    t = {"ahora": 0.0}
    liga, _, _ = liga_papel(tmp_path, reloj=lambda: t["ahora"])
    liga.sincronizar_banco([registro(1)])
    bot = liga.e["bots"]["bot1"]
    for i in range(len(v)):
        t["ahora"] = (int(v["ts"].iloc[i]) + H) / 1000 + 1
        liga.procesar_velas("AAA/USDT:USDT", "1h", v.iloc[: i + 1])
    vivo = pd.DataFrame(bot["trades"])
    assert len(vivo) == len(ops_bt) > 15
    np.testing.assert_allclose(vivo["entrada"], ops_bt["precio_entrada"])
    np.testing.assert_allclose(vivo["salida"], ops_bt["precio_salida"])
    np.testing.assert_allclose(vivo["r"], ops_bt["r"], atol=1e-9)
    assert list(vivo["motivo"]) == list(ops_bt["motivo"])


@pytest.mark.parametrize("salidas", [
    {"stop_tipo": "rango", "stop": 10, "tp_tipo": "atr", "tp": 4.0, "trailing": 3.0, "max_velas": 60},
    {"stop_tipo": "atr", "stop": 2.0, "tp_tipo": "ninguno", "tp": 0.0, "trailing": 0.0, "max_velas": 0,
     "salida_contraria": True},
])
def test_stop_rango_y_salida_contraria_en_vivo_igual_que_el_backtest(tmp_path, salidas):
    est = {"lado": "ambos", "reglas": [{"tipo": "ruptura_donchian", "n": 20}], "salidas": salidas}
    v = serie_mercado(1200, 4, 0.2)
    ops_bt = Evaluador(v, None, Costos(usar_funding=False)).correr(est).operaciones
    ops_bt = ops_bt[ops_bt["motivo"] != "fin de datos"]
    t = {"ahora": 0.0}
    liga, _, _ = liga_papel(tmp_path, reloj=lambda: t["ahora"])
    liga.sincronizar_banco([registro(1, estrategia=est)])
    bot = liga.e["bots"]["bot1"]
    for i in range(len(v)):
        t["ahora"] = (int(v["ts"].iloc[i]) + H) / 1000 + 1
        liga.procesar_velas("AAA/USDT:USDT", "1h", v.iloc[: i + 1])
    vivo = pd.DataFrame(bot["trades"])
    assert len(vivo) == len(ops_bt) > 10
    np.testing.assert_allclose(vivo["entrada"], ops_bt["precio_entrada"])
    np.testing.assert_allclose(vivo["salida"], ops_bt["precio_salida"])
    np.testing.assert_allclose(vivo["r"], ops_bt["r"], atol=1e-9)
    assert list(vivo["motivo"]) == list(ops_bt["motivo"])


# ------------------------------------------------------------------ banco, titulares, jubilación, ascenso
def test_titulares_distintos_y_poco_parecidos(tmp_path):
    dias = [f"2024-02-{d:02d}" for d in range(1, 29)]
    rng = np.random.default_rng(0)
    base = dict(zip(dias, rng.normal(0, 1, 28)))
    liga, mensajes, _ = liga_papel(tmp_path)
    liga.sincronizar_banco([
        registro(1, "AAA/USDT:USDT", diario=base, fitness=9),
        registro(2, "AAA/USDT:USDT", fitness=8),                                   # misma moneda que el 1
        registro(3, "BBB/USDT:USDT", diario={d: v * 1.1 for d, v in base.items()}, fitness=7),  # copia del 1
        registro(4, "CCC/USDT:USDT", diario=dict(zip(dias, rng.normal(0, 1, 28))), fitness=6),
        registro(5, "DDD/USDT:USDT", fitness=5),
    ])
    liga.completar_titulares()
    assert sorted(b["id"] for b in liga.bots("titular")) == ["bot1", "bot4", "bot5"]
    assert any("TITULAR" in m for m in mensajes)


def test_jubilacion_por_caida_y_por_alejarse_del_backtest(tmp_path):
    liga, mensajes, _ = liga_papel(tmp_path)
    liga.sincronizar_banco([registro(1, mc_dd=5.0), registro(2, "BBB/USDT:USDT", r_bt=[0.5, 1.5, -1.0, 2.0] * 50)])
    liga.completar_titulares()
    b1, b2 = liga.e["bots"]["bot1"], liga.e["bots"]["bot2"]
    b1["trades"] = [{"retorno": -0.01, "r": -1, "pnl_usdt": -0.15, "fecha": "x", "rol": "titular"}] * 6  # cae 6% > 5%
    b2["trades"] = [{"retorno": r * 0.01, "r": r, "pnl_usdt": 0, "fecha": "x", "rol": "titular"}
                    for r in [-1.0, -1.0, 0.5] * 8]                                                # muy por debajo
    liga.revisar()
    assert b1["rol"] == "jubilado" and "Monte Carlo" in b1["motivo_jubilacion"]
    assert b2["rol"] == "jubilado" and "backtest" in b2["motivo_jubilacion"]
    assert sum("se jubila" in m for m in mensajes) == 2


def test_pocos_dias_malos_no_jubilan(tmp_path):
    liga, _, _ = liga_papel(tmp_path)
    liga.sincronizar_banco([registro(1, mc_dd=15.0)])
    liga.completar_titulares()
    b = liga.e["bots"]["bot1"]
    b["trades"] = [{"retorno": -0.01, "r": -1, "pnl_usdt": -0.15, "fecha": "x", "rol": "titular"}] * 8  # racha normal
    liga.revisar()
    assert b["rol"] == "titular"


def _trades(rs):
    return [{"retorno": r * 0.01, "r": r, "pnl_usdt": 0, "fecha": "x", "rol": "?"} for r in rs]


def test_ascenso_solo_si_es_claramente_mejor_con_suficientes_operaciones(tmp_path):
    liga, mensajes, _ = liga_papel(tmp_path, cfg_prueba(max_titulares=1))
    liga.sincronizar_banco([registro(1, fitness=9, r_bt=[0.1, -0.5, 0.6] * 50),
                            registro(2, "BBB/USDT:USDT", fitness=8, r_bt=[1.0, -1.0, 1.5] * 50)])
    liga.completar_titulares()
    tit, sup = liga.e["bots"]["bot1"], liga.e["bots"]["bot2"]
    assert tit["rol"] == "titular" and sup["rol"] == "suplente"
    tit["trades"] = _trades([0.2, -0.4, 0.5] * 10)
    sup["trades"] = _trades([1.2, -1.0, 2.0] * 5)  # mejor pero solo 15 operaciones: no alcanza
    liga.revisar()
    assert tit["rol"] == "titular"
    sup["trades"] = _trades([1.2, -1.0, 2.0] * 12)
    liga.revisar()
    assert tit["rol"] == "suplente" and sup["rol"] == "titular"
    assert any("claramente mejor" in m for m in mensajes)


# ------------------------------------------------------------------ cuenta: tamaño, frenos
def _abrir_y_cerrar(liga, bot, pnl_r):
    """Simula una operación del titular con resultado `pnl_r` veces lo arriesgado."""
    riesgo = liga.capital() * 0.01
    bot["posicion"] = {"lado": 1, "entrada": 100.0, "cantidad": riesgo / 2, "riesgo_usdt": riesgo, "dist": 2.0,
                       "stop": 98.0, "tp": 104.0, "trail": 0, "velas": 0, "abierta_ts": 0}
    liga._registrar(bot, 100 + 2 * pnl_r, riesgo * pnl_r, pnl_r, "prueba")
    liga._controlar_cuenta()


def test_freno_diario_por_dos_perdidas_seguidas(tmp_path):
    liga, mensajes, t = liga_papel(tmp_path)
    liga.sincronizar_banco([registro(1)])
    liga.completar_titulares()
    liga.tick()
    bot = liga.e["bots"]["bot1"]
    _abrir_y_cerrar(liga, bot, -1)
    _abrir_y_cerrar(liga, bot, 2)
    _abrir_y_cerrar(liga, bot, -1)
    assert liga.puede_operar() is None  # perdidas no seguidas
    _abrir_y_cerrar(liga, bot, -1)
    assert "freno diario" in liga.puede_operar() and any("Freno diario" in m for m in mensajes)
    t["ahora"] += 86400
    liga.tick()
    assert liga.puede_operar() is None


def test_freno_total_cierra_todo_y_apaga(tmp_path):
    liga, mensajes, _ = liga_papel(tmp_path)
    liga.sincronizar_banco([registro(1), registro(2, "BBB/USDT:USDT")])
    liga.completar_titulares()
    liga.tick()
    b1, b2 = liga.e["bots"]["bot1"], liga.e["bots"]["bot2"]
    b2["posicion"] = {"lado": 1, "entrada": 100.0, "cantidad": 0.05, "riesgo_usdt": 0.1, "dist": 2.0, "stop": 98.0,
                      "tp": None, "trail": 0, "velas": 0, "abierta_ts": 0}
    liga.e["cuenta"]["freno_dia"] = ""
    c = liga.e["cuenta"]
    c["equity"] = 13.0  # cayó 13,3%
    bot = b1
    bot["posicion"] = {"lado": 1, "entrada": 100.0, "cantidad": 0.3, "riesgo_usdt": 0.6, "dist": 2.0, "stop": 98.0,
                       "tp": None, "trail": 0, "velas": 0, "abierta_ts": 0}
    liga._registrar(bot, 98.0, -0.6, -1, "stop-loss")  # 12,4 => 17,3% abajo del máximo
    liga._controlar_cuenta()
    assert liga.e["apagado"] and "cayó" in liga.e["motivo_apagado"]
    assert b2["posicion"] is None  # cerró lo que quedaba abierto
    assert any("FRENO TOTAL" in m for m in mensajes)


def test_titular_respeta_minimos_y_riesgo_total(tmp_path):
    v = serie_mercado(400, 2, 0.2)
    merc = MercadoFalso({("AAA/USDT:USDT", "1h"): v}, minimo=(0.1, 5.0))
    liga, mensajes, t = liga_papel(tmp_path, mercado=merc)
    liga.sincronizar_banco([registro(1)])
    liga.completar_titulares()
    bot = liga.e["bots"]["bot1"]
    merc.minimo = (0.1, 500.0)  # Binance sube el mínimo: imposible con 15 USDT
    liga._abrir(bot, 1, 1.0, v.iloc[-1].to_dict())
    assert bot["posicion"] is None and bot["omitidas"] == 1 and any("no opera" in m for m in mensajes)
    merc.minimo = (0.1, 5.0)
    liga._abrir(bot, 1, 0.5, v.iloc[-1].to_dict())
    p = bot["posicion"]
    assert p is not None and 0 < p["riesgo_usdt"] <= 0.15 + 1e-9  # nunca más del 1% de 15 (redondea para abajo)
    assert p["cantidad"] * p["entrada"] <= 45.0001  # tope 3x


def test_pausa_frena_titulares_pero_no_suplentes(tmp_path):
    v = serie_mercado(400, 2, 0.2)
    liga, _, _ = liga_papel(tmp_path, cfg_prueba(max_titulares=1), mercado=MercadoFalso({("AAA/USDT:USDT", "1h"): v}))
    liga.sincronizar_banco([registro(1), registro(2, "BBB/USDT:USDT")])
    liga.completar_titulares()
    liga.e["pausado"] = True
    tit, sup = liga.e["bots"]["bot1"], liga.e["bots"]["bot2"]
    liga._abrir(tit, 1, 0.5, v.iloc[-1].to_dict())
    liga._abrir(sup, 1, 0.5, v.iloc[-1].to_dict())
    assert tit["posicion"] is None and sup["posicion"] is not None
    assert tit["senales_perdidas"][-1]["motivo"] == "pausado" and "senales_perdidas" not in sup  # queda anotado por qué


# ------------------------------------------------------------------ titular en Binance (simulado)
class EjecutorFalso:
    def __init__(self):
        self.pos = {}
        self.ordenes = []
        self.precio_actual = 100.0

    def preparar(self, s): self.ordenes.append(("preparar", s))
    def precio(self, s): return self.precio_actual
    def posicion(self, s): return self.pos.get(s)

    def abrir(self, s, lado, q):
        self.pos[s] = {"lado": lado, "cantidad": q, "entrada": self.precio_actual}
        self.ordenes.append(("abrir", s, lado, q))
        return self.precio_actual, q

    def proteger(self, s, lado, q, stop, tp):
        self.ordenes.append(("proteger", s, stop, tp))
        return []

    def mover_stop(self, s, lado, q, stop, tp):
        self.ordenes.append(("mover", s, stop))
        return []

    def cerrar(self, s, pos):
        self.pos.pop(s, None)
        self.ordenes.append(("cerrar", s))
        return self.precio_actual, (self.precio_actual - pos["entrada"]) * pos["lado"] * pos["cantidad"]

    def resultado_cierre(self, s, pos, estimado=None):
        return pos["stop"], (pos["stop"] - pos["entrada"]) * pos["lado"] * pos["cantidad"]


def test_titular_en_binance(tmp_path):
    ej = EjecutorFalso()
    mensajes = []
    t = {"ahora": 1_700_000_000.0}
    liga = Liga(cfg_prueba(), str(tmp_path), MercadoFalso(), ej, mensajes.append, reloj=lambda: t["ahora"], modo="testnet")
    liga.sincronizar_banco([registro(1)])
    liga.completar_titulares()
    liga.tick()
    bot = liga.e["bots"]["bot1"]
    assert ("preparar", "AAA/USDT:USDT") in ej.ordenes
    vela = {"ts": 0, "open": 100, "high": 100.5, "low": 99.5, "close": 100}
    liga._abrir(bot, 1, 0.5, vela)
    assert any(o[0] == "abrir" for o in ej.ordenes) and any(o[0] == "proteger" for o in ej.ordenes)
    # sube: el stop móvil se actualiza también en el exchange
    liga._gestionar(bot, {"ts": 1, "open": 100, "high": 103, "low": 99.9, "close": 102.5})
    assert any(o[0] == "mover" for o in ej.ordenes)
    # vigilancia por software: el precio perfora el stop
    ej.precio_actual = bot["posicion"]["stop"] - 0.1
    liga.vigilar()
    assert bot["posicion"] is None and ("cerrar", "AAA/USDT:USDT") in ej.ordenes
    # el exchange cierra solo (stop puesto en Binance)
    ej.precio_actual = 100.0
    liga._abrir(bot, 1, 0.5, vela)
    ej.pos.clear()
    liga._gestionar(bot, vela)
    assert bot["posicion"] is None and "(exchange)" in bot["trades"][-1]["motivo"]
    assert liga.e["cuenta"]["equity"] != 15


def test_posicion_de_papel_sigue_simulada_al_pasar_a_testnet(tmp_path):
    # Abierta en modo papel (estado guardado): en Binance no existe, así que no se da por "cerrada por el exchange"
    liga, _, t = liga_papel(tmp_path)
    liga.sincronizar_banco([registro(1)])
    liga.completar_titulares()
    bot = liga.e["bots"]["bot1"]
    vela = {"ts": 0, "open": 100, "high": 100.5, "low": 99.5, "close": 100}
    liga._abrir(bot, 1, 0.5, vela)
    bot["posicion"].pop("modo")  # estados viejos no tenían el dato
    liga.guardar()
    ej = EjecutorFalso()
    liga = Liga(cfg_prueba(), str(tmp_path), MercadoFalso(), ej, lambda m: None, reloj=lambda: t["ahora"], modo="testnet")
    bot = liga.e["bots"]["bot1"]
    liga._gestionar(bot, {"ts": 1, "open": 100, "high": 100.6, "low": 99.8, "close": 100.2})
    liga.vigilar()
    assert bot["posicion"] is not None and not ej.ordenes  # sigue abierta y simulada
    stop = bot["posicion"]["stop"]
    liga._gestionar(bot, {"ts": 2, "open": 100, "high": 100.1, "low": stop - 1, "close": stop - 0.5})
    assert bot["posicion"] is None and "(exchange)" not in bot["trades"][-1]["motivo"]
    assert bot["trades"][-1]["modo"] == "papel" and not ej.ordenes
    # la siguiente ya se abre en Binance
    liga._abrir(bot, 1, 0.5, vela)
    assert bot["posicion"]["modo"] == "testnet" and any(o[0] == "abrir" for o in ej.ordenes)


def test_estrategias_de_exploracion_nunca_operan_con_plata_real(tmp_path):
    t = {"ahora": 1_700_000_000.0}
    reg = registro(1)
    reg["nivel"] = "exploracion"
    for modo, esperado in (("testnet", "titular"), ("real", "suplente")):
        liga = Liga(cfg_prueba(), str(tmp_path / modo), MercadoFalso(), EjecutorFalso(), lambda m: None,
                    reloj=lambda: t["ahora"], modo=modo)
        liga.sincronizar_banco([reg])
        liga.completar_titulares()
        assert liga.e["bots"]["bot1"]["rol"] == esperado
    assert "🧪" in liga.texto_bots()
    # salvo que se haya graduado operando en vivo (50+ operaciones con ganancia comprobada)
    import numpy as np
    bot = liga.e["bots"]["bot1"]
    bot["trades"] = [{"r": float(r), "retorno": float(r) / 100, "fecha": "2023-11-14T00:00:00+00:00", "rol": "suplente"}
                     for r in np.random.default_rng(1).normal(0.5, 1.0, 60)]
    liga.completar_titulares()
    assert bot["rol"] == "titular"


def distinta(i, simbolo="AAA/USDT:USDT"):
    """Registro con reglas propias (para que no cuente como repetida de otra)."""
    return registro(i, simbolo, estrategia={**TENDENCIA, "reglas": [{"tipo": "ruptura_donchian", "n": 20 + i}]})


def test_suplentes_repartidos_entre_monedas(tmp_path):
    liga, _, _ = liga_papel(tmp_path, cfg_prueba(max_suplentes=6, max_suplentes_por_moneda=2))
    # el banco viejo solo tenía AAA: se llenaron todos los lugares con esa moneda
    liga.L["max_suplentes_por_moneda"] = 0
    liga.sincronizar_banco([distinta(i) for i in range(6)])
    liga.L["max_suplentes_por_moneda"] = 2
    liga.e["bots"]["bot5"]["trades"].append({"r": 1.0, "fecha": "2023-11-14T00:00:00+00:00", "rol": "suplente"})
    # llegan estrategias de otras monedas: hay lugar para ellas
    nuevos = liga.sincronizar_banco([distinta(i) for i in range(6)] + [distinta(10, "BBB/USDT:USDT"),
                                     distinta(11, "CCC/USDT:USDT"), distinta(12, "CCC/USDT:USDT"),
                                     distinta(13, "CCC/USDT:USDT")])
    por_moneda = {}
    for b in liga.bots("suplente"):
        por_moneda[b["simbolo"][:3]] = por_moneda.get(b["simbolo"][:3], 0) + 1
    assert por_moneda == {"AAA": 2, "BBB": 1, "CCC": 2}
    assert "bot5" in liga.e["bots"]  # la que ya operó no se saca
    assert set(nuevos) == {"bot10", "bot11", "bot12"}


def test_primero_las_estrictas(tmp_path):
    liga, _, _ = liga_papel(tmp_path, cfg_prueba(max_titulares=1))
    flojo = registro(1, fitness=50)
    flojo["nivel"] = "exploracion"
    liga.sincronizar_banco([flojo, registro(2, "BBB/USDT:USDT", fitness=5)])
    liga.completar_titulares()
    assert liga.e["bots"]["bot2"]["rol"] == "titular" and liga.e["bots"]["bot1"]["rol"] == "suplente"


def test_no_elige_titulares_que_no_pueden_operar_con_15_usdt(tmp_path):
    class MercadoMinimos(MercadoFalso):
        def limites(self, simbolo):
            return {"BTC/USDT:USDT": (0.001, 100.0), "ETH/USDT:USDT": (0.001, 20.0)}.get(simbolo, (0.1, 5.0))
    liga, _, _ = liga_papel(tmp_path, mercado=MercadoMinimos())
    stop_ancho = {**TENDENCIA, "salidas": {**TENDENCIA["salidas"], "stop_tipo": "pct", "stop": 5.0}}
    liga.sincronizar_banco([
        registro(1, "BTC/USDT:USDT", fitness=9),                      # mínimo 100 > 45 (3x de 15): imposible
        registro(2, "ETH/USDT:USDT", estrategia=stop_ancho, fitness=8),  # stop 5%: 0,15/0,05 = 3 USDT < 20
        registro(3, "XRP/USDT:USDT", fitness=7),
    ])
    liga.completar_titulares()
    assert [b["id"] for b in liga.bots("titular")] == ["bot3"]


def test_titular_que_nunca_llega_al_minimo_deja_su_lugar(tmp_path):
    v = serie_mercado(400, 2, 0.2)
    merc = MercadoFalso({("AAA/USDT:USDT", "1h"): v}, minimo=(0.1, 5.0))
    liga, mensajes, _ = liga_papel(tmp_path, cfg_prueba(max_titulares=1), mercado=merc)
    liga.sincronizar_banco([registro(1, fitness=9), registro(2, "BBB/USDT:USDT", fitness=5)])
    liga.completar_titulares()
    bot = liga.e["bots"]["bot1"]
    for _ in range(3):
        liga._abrir(bot, 1, 50.0, v.iloc[-1].to_dict())  # ATR enorme: stop muy lejos, no llega al mínimo
    assert bot["posicion"] is None and bot["omitidas_seguidas"] == 3
    liga.revisar()
    assert bot["rol"] == "suplente" and bot["no_operable"]
    assert liga.e["bots"]["bot2"]["rol"] == "titular"
    assert any("dejo su lugar" in m.lower() for m in mensajes)


def test_con_100_usdt_si_puede_operar_btc_y_eth(tmp_path):
    class MercadoMinimos(MercadoFalso):
        def limites(self, simbolo):
            return {"BTC/USDT:USDT": (0.001, 100.0), "ETH/USDT:USDT": (0.001, 20.0)}.get(simbolo, (0.1, 5.0))
    liga, _, _ = liga_papel(tmp_path, cfg_prueba(capital=100), mercado=MercadoMinimos())
    stop_ancho = {**TENDENCIA, "salidas": {**TENDENCIA["salidas"], "stop_tipo": "pct", "stop": 5.0}}
    liga.sincronizar_banco([registro(1, "BTC/USDT:USDT", fitness=9),
                            registro(2, "ETH/USDT:USDT", estrategia=stop_ancho, fitness=8)])
    liga.completar_titulares()
    assert sorted(b["id"] for b in liga.bots("titular")) == ["bot1", "bot2"]  # 1% de 100 / 5% = 20 USDT: alcanza


def test_bot_con_datos_externos_los_pide_en_vivo_y_si_fallan_no_entra(tmp_path):
    v = serie_mercado(300, 2, 0.2)
    pedidos = []

    class MercadoExt(MercadoFalso):
        falla = False

        def externos_vivo(self, simbolo, tf, velas, ahora_ms):
            pedidos.append(simbolo)
            if self.falla:
                raise ConnectionError("sin internet")
            return {"fng": np.full(len(velas), 10.0), "funding": np.zeros(len(velas)), "btc": velas["close"].to_numpy()}

    merc = MercadoExt({("AAA/USDT:USDT", "1h"): v})
    t = {"ahora": (int(v["ts"].iloc[-1]) + H) / 1000 + 1}
    liga, mensajes, _ = liga_papel(tmp_path, reloj=lambda: t["ahora"], mercado=merc)
    siempre = {"lado": "long", "reglas": [{"tipo": "miedo_codicia", "op": "<", "nivel": 30}],
               "salidas": {"stop_tipo": "atr", "stop": 2.0, "tp_tipo": "atr", "tp": 4.0, "trailing": 0.0, "max_velas": 0}}
    liga.sincronizar_banco([registro(1, estrategia=siempre), registro(2, "AAA/USDT:USDT")])
    liga.procesar_velas("AAA/USDT:USDT", "1h", v.iloc[:-1])  # al entrar, arrancan desde la próxima vela
    assert pedidos == [] and liga.e["bots"]["bot1"]["posicion"] is None
    liga.procesar_velas("AAA/USDT:USDT", "1h", v)
    assert pedidos == ["AAA/USDT:USDT"]                     # se pide una sola vez por vela y solo si hace falta
    assert liga.e["bots"]["bot1"]["posicion"] is not None    # miedo 10 < 30: entra
    liga.e["bots"]["bot1"]["posicion"] = None
    merc.falla = True
    t["ahora"] += 3600
    v2 = pd.concat([v, v.tail(1).assign(ts=v["ts"].iloc[-1] + H)], ignore_index=True)
    liga.procesar_velas("AAA/USDT:USDT", "1h", v2)
    assert liga.e["bots"]["bot1"]["posicion"] is None and any("datos externos" in m for m in mensajes)


def test_resumen_nocturno_muestra_la_practica_de_los_suplentes(tmp_path):
    liga, _, _ = liga_papel(tmp_path)
    liga.sincronizar_banco([registro(1), registro(2, "BBB/USDT:USDT")])
    sup = liga.e["bots"]["bot2"]
    hoy = liga.ahora().isoformat(timespec="seconds")
    sup["trades"] += [{"fecha": hoy, "rol": "suplente", "r": 1.5}, {"fecha": hoy, "rol": "suplente", "r": -1.0}]
    texto = liga.texto_noche()
    assert "Suplentes (práctica): 2 operación(es), 1 ganada(s), +0.5R." in texto


def test_resumen_nocturno_cuenta_las_ultimas_24_horas(tmp_path):
    # 22 h de Montevideo = 01 h UTC: una operación de la tarde quedó en el día UTC anterior y igual tiene que aparecer
    from datetime import datetime, timezone
    ahora = datetime(2026, 10, 19, 1, 0, tzinfo=timezone.utc).timestamp()
    liga, _, _ = liga_papel(tmp_path, reloj=lambda: ahora)
    liga.sincronizar_banco([registro(1)])
    liga.completar_titulares()
    tit = liga.e["bots"]["bot1"]
    tit["trades"] += [{"fecha": "2026-10-18T19:21:08+00:00", "rol": "titular", "r": 2.4, "pnl_usdt": 2.44},
                      {"fecha": "2026-10-17T19:00:00+00:00", "rol": "titular", "r": -1.0, "pnl_usdt": -1.0}]
    texto = liga.texto_noche()
    assert "ganó 2.44 dólares con 1 operaciones" in texto


def test_examen_de_graduacion_solo_informa(tmp_path):
    t = {"ahora": 1_700_000_000.0}
    liga, _, _ = liga_papel(tmp_path, reloj=lambda: t["ahora"])
    liga.sincronizar_banco([registro(1), {**registro(2, "BBB/USDT:USDT"), "nivel": "exploracion"}])
    texto = liga.texto_preparacion()
    assert "EXAMEN DE GRADUACIÓN" in texto and "Faltan 3 de 5" in texto
    # un bot estricto con 30 operaciones ganadoras parecidas a sus pruebas cuenta como "probado"; uno 🧪 nunca
    for b in liga.e["bots"].values():
        b["trades"] = [{"r": 0.8, "retorno": 0.008, "fecha": "2023-11-14T00:00:00+00:00", "rol": "suplente"}] * 30
    assert [b["id"] for b in liga.bots_listos()] == ["bot1"]  # la 🧪 con 30 todavía no alcanza
    import numpy as np
    sup = liga.e["bots"]["bot2"]
    rs = np.random.default_rng(1).normal(0.4, 1.0, 60)              # 60 operaciones con ganancia clara
    sup["trades"] = [{"r": float(r), "retorno": float(r) / 100, "fecha": "2023-11-14T00:00:00+00:00",
                      "rol": "suplente"} for r in rs]
    assert liga.graduado(sup)
    sup["trades"] = [{**t, "r": float(r)} for t, r in zip(sup["trades"], np.random.default_rng(2).normal(0.0, 1.0, 60))]
    assert not liga.graduado(sup)                                     # ganar por momentos no alcanza
    t["ahora"] += 5 * 7 * 86400
    texto = liga.texto_preparacion()
    assert "Faltan 1 de 5" in texto and "Demo Trading" in texto and liga.modo == "papel"  # no cambia de modo solo


def test_la_practica_cuenta_desde_lo_mas_antiguo(tmp_path):
    t = {"ahora": 1_700_000_000.0}
    liga, _, _ = liga_papel(tmp_path, reloj=lambda: t["ahora"])
    liga.sincronizar_banco([registro(1)])
    liga.e["creado"] = liga.ahora().isoformat(timespec="seconds")
    liga.e["bots"]["bot1"]["desde"] = "2023-11-01T00:00:00+00:00"   # el bot ya practicaba desde antes
    liga.guardar()
    t["ahora"] += 3600
    otra, _, _ = liga_papel(tmp_path, reloj=lambda: t["ahora"])
    assert otra.e["creado"] == "2023-11-01T00:00:00+00:00"


def test_guardar_desde_varios_hilos_a_la_vez(tmp_path):
    import threading
    liga, _, _ = liga_papel(tmp_path)
    liga.sincronizar_banco([registro(i) for i in range(5)])
    errores = []

    def guardar_mucho():
        try:
            for _ in range(50):
                liga.guardar()
        except Exception as e:  # noqa: BLE001
            errores.append(e)
    hilos = [threading.Thread(target=guardar_mucho) for _ in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert not errores
    assert not [n for n in os.listdir(tmp_path) if n.endswith(".tmp")]


def test_orden_rechazada_por_binance_no_rompe_nada(tmp_path):
    class EjecutorSinMargen(EjecutorFalso):
        def abrir(self, s, lado, q):
            raise RuntimeError('binanceusdm {"code":-2019,"msg":"Margin is insufficient."}')
    ej = EjecutorSinMargen()
    mensajes = []
    t = {"ahora": 1_700_000_000.0}
    liga = Liga(cfg_prueba(), str(tmp_path), MercadoFalso(), ej, mensajes.append, reloj=lambda: t["ahora"], modo="testnet")
    liga.sincronizar_banco([registro(1)])
    liga.completar_titulares()
    bot = liga.e["bots"]["bot1"]
    liga._abrir(bot, 1, 0.5, {"ts": 0, "open": 100, "high": 100.5, "low": 99.5, "close": 100})
    assert bot["posicion"] is None
    assert "rechazó" in bot["senales_perdidas"][-1]["motivo"]
    assert any("billetera de Futuros" in m for m in mensajes)


def test_no_entran_suplentes_repetidas(tmp_path):
    liga, mensajes, _ = liga_papel(tmp_path, cfg_prueba(max_titulares=0))
    otra = {**TENDENCIA, "reglas": [{"tipo": "ruptura_donchian", "n": 55}]}
    nuevos = liga.sincronizar_banco([registro(1), registro(2), registro(3, estrategia=otra),
                                     registro(4, "BBB/USDT:USDT")])
    # bot2 tiene las mismas reglas de entrada que bot1 en la misma moneda y temporalidad: no entra
    assert nuevos == ["bot1", "bot3", "bot4"]
    # resultados diarios casi iguales también cuentan como repetida
    diario = {f"2024-01-{d:02d}": float(np.sin(d)) for d in range(1, 29)}
    liga2, _, _ = liga_papel(tmp_path / "b", cfg_prueba(max_titulares=0))
    a = registro(5, estrategia=otra, diario=diario)
    b = registro(6, diario={k: v * 1.01 for k, v in diario.items()})
    assert liga2.sincronizar_banco([a, b]) == ["bot5"]


def test_se_sacan_las_repetidas_que_ya_estaban(tmp_path):
    liga, _, _ = liga_papel(tmp_path, cfg_prueba(max_titulares=0, max_correlacion_suplentes=2.0))
    # estado viejo: entraron tres iguales (antes no se controlaba)
    for i in (1, 2, 3):
        liga.e["bots"][f"bot{i}"] = {**liga.e["bots"].get("x", {}), "id": f"bot{i}", "rol": "suplente",
                                     "simbolo": "AAA/USDT:USDT", "tf": "1h", "estrategia": TENDENCIA,
                                     "fitness": 1.0, "posicion": None, "trades": [], "retornos_diarios": {}}
    liga.e["bots"]["bot2"]["trades"] = [{"r": -1.0}, {"r": 2.0}]
    liga.sincronizar_banco([])
    assert list(liga.e["bots"]) == ["bot2"]  # queda la que más operó


def test_bots_muestra_tambien_los_peores_suplentes(tmp_path):
    liga, _, _ = liga_papel(tmp_path, cfg_prueba(max_titulares=0, max_suplentes=30, max_suplentes_por_moneda=30))
    liga.sincronizar_banco([distinta(i) for i in range(14)])
    liga.e["bots"]["bot0"]["trades"] = [{"r": 3.0, "pnl_usdt": 0.0, "fecha": "2023-11-14T00:00:00+00:00", "rol": "suplente"}]
    liga.e["bots"]["bot7"]["trades"] = [{"r": -2.0, "pnl_usdt": 0.0, "fecha": "2023-11-14T00:00:00+00:00", "rol": "suplente"}]
    texto = liga.texto_bots()
    assert "SUPLENTES (practican simulados): 14" in texto
    assert "bot0" in texto and "bot7" in texto and "Los 5 peores:" in texto


def test_bot_recien_llegado_no_opera_la_senal_de_una_vela_vieja(tmp_path):
    v = serie_mercado(300, 2, 0.2)
    t = {"ahora": (int(v["ts"].iloc[-1]) + H) / 1000 + 1}
    liga, _, _ = liga_papel(tmp_path, reloj=lambda: t["ahora"])
    siempre = {"lado": "long", "reglas": [{"tipo": "rsi_filtro", "n": 14, "op": ">", "nivel": 0}],
               "salidas": {"stop_tipo": "atr", "stop": 2.0, "tp_tipo": "ninguno", "tp": 0.0, "trailing": 0.0, "max_velas": 0}}
    liga.sincronizar_banco([registro(1, estrategia=siempre)])
    bot = liga.e["bots"]["bot1"]
    liga.procesar_velas("AAA/USDT:USDT", "1h", v)          # la última vela cerró antes de que entrara
    assert bot["posicion"] is None and bot["ultima_vela_ts"] == int(v["ts"].iloc[-1])
    t["ahora"] += 3600
    v2 = pd.concat([v, v.tail(1).assign(ts=v["ts"].iloc[-1] + H)], ignore_index=True)
    liga.procesar_velas("AAA/USDT:USDT", "1h", v2)          # la primera vela nueva sí cuenta
    assert bot["posicion"] is not None


def test_dos_titulares_por_moneda_pero_una_posicion_a_la_vez(tmp_path):
    ej = EjecutorFalso()
    t = {"ahora": 1_700_000_000.0}
    liga = Liga(cfg_prueba(max_titulares_por_moneda=2), str(tmp_path), MercadoFalso(), ej, lambda m: None,
                reloj=lambda: t["ahora"], modo="testnet")
    liga.sincronizar_banco([distinta(1), distinta(2), registro(3)])  # tres estrategias distintas de la misma moneda
    liga.completar_titulares()
    titulares = [b["id"] for b in liga.bots("titular")]
    assert len(titulares) == 2  # dos por moneda como máximo, y distintas entre sí
    a, b = (liga.e["bots"][i] for i in titulares)
    vela = {"ts": 0, "open": 100, "high": 100.5, "low": 99.5, "close": 100}
    liga._abrir(a, 1, 0.5, vela)
    assert a["posicion"] is not None
    liga._abrir(b, -1, 0.5, vela)  # la moneda ya tiene una posición en Binance: no se mezcla
    assert b["posicion"] is None and "ya tiene una posición abierta" in b["senales_perdidas"][-1]["motivo"]
    assert sum(o[0] == "abrir" for o in ej.ordenes) == 1


def test_ajustes_por_temporalidad_en_la_fabrica():
    from fabrica.config import cargar_config
    g = cargar_config()["generador"]
    g15 = {**g, **(g.get("por_temporalidad") or {}).get("15m", {})}
    g1h = {**g, **(g.get("por_temporalidad") or {}).get("1h", {})}
    assert g15["candidatas"] > g1h["candidatas"] and g15["operaciones_por_anio_objetivo"] > g1h["operaciones_por_anio_objetivo"]
