"""Liga y bots en vivo: mismas reglas que el backtest, protección de la cuenta, ascensos y jubilaciones."""
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
    liga.procesar_velas("AAA/USDT:USDT", "1h", v)
    assert pedidos == ["AAA/USDT:USDT"]                     # se pide una sola vez por vela y solo si hace falta
    assert liga.e["bots"]["bot1"]["posicion"] is not None    # miedo 10 < 30: entra
    liga.e["bots"]["bot1"]["posicion"] = None
    merc.falla = True
    t["ahora"] += 3600
    v2 = pd.concat([v, v.tail(1).assign(ts=v["ts"].iloc[-1] + H)], ignore_index=True)
    liga.procesar_velas("AAA/USDT:USDT", "1h", v2)
    assert liga.e["bots"]["bot1"]["posicion"] is None and any("datos externos" in m for m in mensajes)
