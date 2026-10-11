"""Pruebas de punta a punta del bot en modo papel y con un exchange simulado."""
import csv
import os
from dataclasses import replace

import pytest

from tests.conftest import TF_MS, buscar_senal
from trader import riesgo
from trader.bot import Bot
from trader.broker import BrokerPapel
from trader.estado import Estado
from trader.registro import RegistroOperaciones


class ClienteFalso:
    """Imita la parte de ccxt que usa el bot."""

    def __init__(self, velas, precio, min_cantidad=0.1, min_nocional=5.0):
        self.velas = velas
        self.precio = precio
        self.limites = {"amount": {"min": min_cantidad}, "cost": {"min": min_nocional}}

    def load_markets(self):
        return {}

    def market(self, simbolo):
        return {"limits": self.limites}

    def fetch_ohlcv(self, simbolo, timeframe, limit):
        return self.velas[-limit:]

    def fetch_ticker(self, simbolo):
        return {"last": self.precio}

    def amount_to_precision(self, simbolo, cantidad):
        return str(riesgo.redondear_abajo(cantidad, 0.1))

    def price_to_precision(self, simbolo, precio):
        return str(round(precio, 4))


class IAFalsa:
    def __init__(self, score=80, disponible=True):
        self.score = score
        self.disponible = disponible
        self.llamadas = 0

    def presupuesto_disponible(self):
        return self.disponible

    def uso(self):
        return {"dia": 0, "max_dia": 20, "semana": 0, "max_semana": 80}

    def evaluar(self, df, lado):
        self.llamadas += 1
        if self.score is None:
            return False, None, "IA no disponible"
        return self.score >= 60, self.score, "motivo de prueba"


class Entorno:
    def __init__(self, cfg, tmp_path, lado="LONG", ia=None, **kw_cliente):
        velas, i = buscar_senal(lado)
        self.velas_senal = velas[: i + 1]
        formando = list(velas[i + 1]) if i + 1 < len(velas) else list(velas[i])
        formando[0] = self.velas_senal[-1][0] + TF_MS
        self.cliente = ClienteFalso(self.velas_senal + [formando], self.velas_senal[-1][4], **kw_cliente)
        self.ahora = (self.velas_senal[-1][0] + TF_MS) / 1000 + 5  # 5 s después del cierre
        self.estado = Estado(os.path.join(tmp_path, "estado.json"))
        self.broker = BrokerPapel(cfg, self.cliente, self.estado)
        self.registro = RegistroOperaciones(os.path.join(tmp_path, "operaciones.csv"))
        self.ia = ia or IAFalsa()
        self.mensajes = []
        self.bot = Bot(cfg, self.broker, self.estado, self.ia, self.registro, self.mensajes.append,
                       reloj=lambda: self.ahora)
        self.bot.iniciar()

    def ultimo(self):
        return self.mensajes[-1]


def test_abre_long_y_cierra_en_take_profit(cfg, tmp_path):
    e = Entorno(cfg, tmp_path)
    e.bot.ciclo()
    pos = e.estado["posicion"]
    assert pos and pos["lado"] == "LONG"
    precio = e.cliente.precio
    assert pos["cantidad"] == pytest.approx(riesgo.redondear_abajo(15 * 0.9 * 3 / precio, 0.1))
    assert pos["sl"] == pytest.approx(precio * 0.97) and pos["tp"] == pytest.approx(precio * 1.06)
    assert "APERTURA LONG" in e.ultimo()
    assert e.estado["operaciones_hoy"] == 1

    e.cliente.precio = precio * 1.03  # aún no toca
    e.ahora += 30
    e.bot.ciclo()
    assert e.estado["posicion"]

    e.cliente.precio = precio * 1.061
    e.ahora += 30
    e.bot.ciclo()
    assert e.estado["posicion"] is None
    esperado = riesgo.calcular_pnl("LONG", precio, precio * 1.061, pos["cantidad"], 0.05)
    filas = list(csv.DictReader(open(tmp_path / "operaciones.csv")))
    assert len(filas) == 1
    assert filas[0]["lado"] == "LONG" and "take-profit" in filas[0]["motivo_cierre"]
    assert float(filas[0]["resultado_usdt"]) == pytest.approx(esperado, abs=1e-6)
    assert e.broker.saldo() == pytest.approx(15 + esperado)
    assert "CIERRE LONG" in e.ultimo()


def test_abre_short_y_cierra_en_stop_loss(cfg, tmp_path):
    e = Entorno(cfg, tmp_path, lado="SHORT")
    e.bot.ciclo()
    pos = e.estado["posicion"]
    assert pos["lado"] == "SHORT"
    e.cliente.precio = pos["entrada"] * 1.031
    e.ahora += 30
    e.bot.ciclo()
    fila = e.registro.ultimas(1)[0]
    assert "stop-loss" in fila["motivo_cierre"] and float(fila["resultado_usdt"]) < 0


def test_misma_vela_no_se_evalua_dos_veces(cfg, tmp_path):
    e = Entorno(cfg, tmp_path, ia=IAFalsa(score=10))
    e.bot.ciclo()
    e.ahora += 30
    e.bot.ciclo()
    assert e.ia.llamadas == 1


def test_ia_rechaza_o_falla_no_opera(cfg, tmp_path):
    e = Entorno(cfg, tmp_path, ia=IAFalsa(score=40))
    e.bot.ciclo()
    assert e.estado["posicion"] is None and "descartada" in e.ultimo()

    e2 = Entorno(cfg, tmp_path / "b", ia=IAFalsa(score=None))
    e2.bot.ciclo()
    assert e2.estado["posicion"] is None and "IA falló" in e2.ultimo()

    e3 = Entorno(cfg, tmp_path / "c", ia=IAFalsa(disponible=False))
    e3.bot.ciclo()
    assert e3.estado["posicion"] is None and "presupuesto" in e3.ultimo() and e3.ia.llamadas == 0


def test_minimo_del_par_no_alcanza(cfg, tmp_path):
    e = Entorno(cfg, tmp_path, min_nocional=100.0)
    e.bot.ciclo()
    assert e.estado["posicion"] is None
    assert "mínimo del par" in e.ultimo() and e.ia.llamadas == 0


def test_pausado_no_abre(cfg, tmp_path):
    e = Entorno(cfg, tmp_path)
    e.bot.cmd_pausar()
    e.bot.ciclo()
    assert e.estado["posicion"] is None and e.ia.llamadas == 0


def test_maximo_operaciones_por_dia(cfg, tmp_path):
    e = Entorno(cfg, tmp_path)
    e.estado["operaciones_hoy"] = 5
    e.bot.ciclo()
    assert e.estado["posicion"] is None and e.ia.llamadas == 0


def test_corte_diario_por_perdida(cfg, tmp_path):
    e = Entorno(cfg, tmp_path)
    papel = dict(e.estado["papel"]); papel["saldo"] = 11.9; e.estado["papel"] = papel  # -20,7% en el día
    e.bot.ciclo()
    assert e.estado["corte_dia"] == e.bot.hoy()
    assert e.estado["posicion"] is None and e.ia.llamadas == 0
    assert any("CORTE DE SEGURIDAD" in m for m in e.mensajes)
    e.ahora += 86_400  # al día siguiente se libera
    e.bot.ciclo()
    assert not e.bot.corte_activo()
    assert e.estado["saldo_inicio_dia"] == pytest.approx(11.9)


def test_apagado_por_saldo_minimo(cfg, tmp_path):
    e = Entorno(cfg, tmp_path)
    papel = dict(e.estado["papel"]); papel["saldo"] = 9.5; e.estado["papel"] = papel
    e.bot.ciclo()
    assert e.estado["apagado"] and "BOT APAGADO" in e.ultimo()
    assert e.estado["posicion"] is None
    assert "No se puede reactivar" in e.bot.cmd_reactivar()


def test_comando_cerrar_y_operaciones(cfg, tmp_path):
    e = Entorno(cfg, tmp_path)
    assert e.bot.cmd_cerrar() == "No hay posición abierta."
    e.bot.ciclo()
    assert "LONG" in e.bot.cmd_estado()
    e.bot.cmd_cerrar()
    assert e.estado["posicion"] is None
    fila = e.registro.ultimas(1)[0]
    assert fila["motivo_cierre"] == "cierre manual (/cerrar)"
    # cerrar al mismo precio => solo pierde comisiones
    assert float(fila["resultado_usdt"]) == pytest.approx(-2 * float(fila["entrada"]) * float(fila["cantidad"]) * 0.0005, abs=1e-6)
    assert "Últimas operaciones" in e.bot.cmd_operaciones()
    assert "Total" in e.bot.cmd_estado()


def test_real_sin_confirmacion_no_opera(cfg, tmp_path):
    cfg_real = replace(cfg, modo="real", confirmar_real=False)
    e = Entorno(cfg_real, tmp_path)
    assert e.estado["apagado"] and "CONFIRMAR_REAL" in e.estado["motivo_apagado"]
    e.bot.ciclo()
    assert e.estado["posicion"] is None and e.ia.llamadas == 0


# ---------------------------------------------------------------- exchange simulado
class BrokerExchangeFalso:
    modo = "testnet"

    def __init__(self, pos=None):
        self.pos = pos
        self.protecciones = []
        self.cancelaciones = 0
        self.min_cantidad, self.min_nocional = 0.1, 5
        self.saldo_val = 15.0

    def cargar_mercado(self): pass
    def preparar(self): pass
    def saldo(self): return self.saldo_val
    def posicion(self): return self.pos
    def precio(self): return 0.5
    def velas(self, limite): return []
    def cancelar_protecciones(self): self.cancelaciones += 1

    def colocar_protecciones(self, lado, cantidad, sl, tp):
        self.protecciones.append((lado, cantidad, sl, tp))
        return []

    def cierre_externo(self, pos):
        return pos["tp"], riesgo.calcular_pnl(pos["lado"], pos["entrada"], pos["tp"], pos["cantidad"], 0.05)


def bot_exchange(cfg, tmp_path, broker, pos_guardada=None):
    estado = Estado(os.path.join(tmp_path, "estado.json"))
    estado["posicion"] = pos_guardada
    mensajes = []
    bot = Bot(replace(cfg, modo="testnet"), broker, estado, IAFalsa(),
              RegistroOperaciones(os.path.join(tmp_path, "op.csv")), mensajes.append, reloj=lambda: 1_760_000_000)
    bot.iniciar()
    return bot, estado, mensajes


def test_reinicio_adopta_posicion_del_exchange(cfg, tmp_path):
    broker = BrokerExchangeFalso(pos={"lado": "SHORT", "cantidad": 80.0, "entrada": 0.5})
    bot, estado, mensajes = bot_exchange(cfg, tmp_path, broker)
    pos = estado["posicion"]
    assert pos["lado"] == "SHORT" and pos["sl"] == pytest.approx(0.515) and pos["tp"] == pytest.approx(0.47)
    assert broker.protecciones == [("SHORT", 80.0, pos["sl"], pos["tp"])]
    assert any("adopto" in m for m in mensajes)
    # con una posición abierta nunca abre otra
    bot.abrir_posicion("LONG", None)
    assert estado["posicion"]["lado"] == "SHORT"


def test_reinicio_registra_posicion_cerrada_mientras_estaba_apagado(cfg, tmp_path):
    guardada = {"lado": "LONG", "cantidad": 80.0, "entrada": 0.5, "sl": 0.485, "tp": 0.53,
                "abierta_ts": 0, "abierta_iso": "2026-10-11T00:00:00+00:00"}
    bot, estado, _ = bot_exchange(cfg, tmp_path, BrokerExchangeFalso(pos=None), pos_guardada=guardada)
    assert estado["posicion"] is None
    fila = bot.registro.ultimas(1)[0]
    assert float(fila["salida"]) == pytest.approx(0.53) and float(fila["resultado_usdt"]) > 0


def test_cierre_por_orden_del_exchange_detectado(cfg, tmp_path):
    broker = BrokerExchangeFalso(pos={"lado": "LONG", "cantidad": 80.0, "entrada": 0.5})
    bot, estado, mensajes = bot_exchange(cfg, tmp_path, broker)
    broker.pos = None  # el TP del exchange se ejecutó
    bot.ciclo()
    assert estado["posicion"] is None
    fila = bot.registro.ultimas(1)[0]
    assert fila["motivo_cierre"] == "take-profit (orden del exchange)"


def test_posicion_huerfana_se_adopta_en_el_ciclo(cfg, tmp_path):
    broker = BrokerExchangeFalso(pos=None)
    bot, estado, mensajes = bot_exchange(cfg, tmp_path, broker)
    assert estado["posicion"] is None
    broker.pos = {"lado": "LONG", "cantidad": 80.0, "entrada": 0.5}  # apareció sin que el bot la registre
    bot.ciclo()
    assert estado["posicion"]["lado"] == "LONG" and broker.protecciones
