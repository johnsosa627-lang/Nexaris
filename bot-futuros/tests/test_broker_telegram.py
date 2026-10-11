import pytest

from trader.broker import BrokerBinance
from trader.config import Config
from trader.telegram_bot import Telegram


class CcxtFalso:
    def __init__(self):
        self.ordenes = []
        self.posiciones = [{"symbol": "XRP/USDT:USDT", "contracts": 80, "side": "long", "entryPrice": 0.5,
                            "info": {"positionAmt": "80"}}]
        self.trades = []

    def fetch_positions(self, simbolos):
        return self.posiciones

    def fetch_balance(self):
        return {"info": {"assets": [{"asset": "BTC", "walletBalance": "1"},
                                    {"asset": "USDT", "walletBalance": "14.25"}]}, "USDT": {"total": 99}}

    def create_order(self, simbolo, tipo, lado, cantidad, precio=None, params=None):
        self.ordenes.append((tipo, lado, cantidad, params or {}))
        return {"average": 0.53, "filled": cantidad}

    def cancel_all_orders(self, simbolo, params=None):
        return []

    def fetch_my_trades(self, simbolo, since=None):
        return self.trades

    def fetch_ticker(self, simbolo):
        return {"last": 0.52}

    def price_to_precision(self, simbolo, precio):
        return f"{precio:.4f}"


def test_posicion_saldo_y_protecciones():
    cli = CcxtFalso()
    b = BrokerBinance(Config(modo="testnet"), cli)
    assert b.posicion() == {"lado": "LONG", "cantidad": 80.0, "entrada": 0.5}
    assert b.saldo() == pytest.approx(14.25)
    assert b.colocar_protecciones("LONG", 80, 0.485, 0.53) == []
    sl, tp = cli.ordenes
    assert sl[1] == "sell" and sl[3] == {"stopLossPrice": 0.485, "reduceOnly": True}
    assert tp[3] == {"takeProfitPrice": 0.53, "reduceOnly": True}
    cli.posiciones = [{"symbol": "XRP/USDT:USDT", "contracts": 0, "side": None, "entryPrice": 0, "info": {}}]
    assert b.posicion() is None


def test_cierre_usa_pnl_real_de_los_trades():
    cli = CcxtFalso()
    cli.trades = [
        {"side": "buy", "amount": 80, "price": 0.5, "fee": {"cost": 0.02, "currency": "USDT"}, "info": {"realizedPnl": "0"}},
        {"side": "sell", "amount": 80, "price": 0.53, "fee": {"cost": 0.0212, "currency": "USDT"}, "info": {"realizedPnl": "2.4"}},
    ]
    b = BrokerBinance(Config(modo="testnet"), cli)
    pos = {"lado": "LONG", "cantidad": 80, "entrada": 0.5, "sl": 0.485, "tp": 0.53, "abierta_ts": 0}
    salida, pnl = b.cerrar(pos)
    assert cli.ordenes[0] == ("market", "sell", 80.0, {"reduceOnly": True})
    assert salida == pytest.approx(0.53) and pnl == pytest.approx(2.4 - 0.0412)


def test_telegram_solo_responde_al_chat_autorizado(monkeypatch):
    tg = Telegram("token", "123")
    enviados = []
    monkeypatch.setattr(tg, "enviar", enviados.append)
    llamadas = []
    tg.registrar("/pausar", lambda: llamadas.append(1) or "pausado")
    tg.procesar({"message": {"chat": {"id": 999}, "text": "/pausar"}})
    assert llamadas == [] and enviados == []
    tg.procesar({"message": {"chat": {"id": 123}, "text": "/pausar@MiBot"}})
    assert llamadas == [1] and enviados == ["pausado"]
    tg.procesar({"message": {"chat": {"id": 123}, "text": "/nada"}})
    assert "Comandos" in enviados[-1]
