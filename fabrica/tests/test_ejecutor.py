import pytest

from fabrica.ejecutor import EjecutorBinance, Mercado
from tests.conftest import H, T0


class CcxtFalso:
    def __init__(self):
        self.ordenes, self.config = [], []
        self.trades = []
        self.posiciones = [{"symbol": "XRP/USDT:USDT", "contracts": 30, "side": "short", "entryPrice": 0.5, "info": {}}]

    def load_markets(self): return {}
    def market(self, s): return {"limits": {"amount": {"min": 0.1}, "cost": {"min": 5}}}
    def amount_to_precision(self, s, q): return f"{int(q * 10) / 10}"
    def price_to_precision(self, s, p): return f"{p:.4f}"
    def set_position_mode(self, *a): self.config.append("one-way")
    def set_margin_mode(self, m, s): self.config.append(m)
    def set_leverage(self, n, s): self.config.append(n)
    def fetch_positions(self, s): return self.posiciones
    def fetch_ticker(self, s): return {"last": 0.49}
    def cancel_all_orders(self, s, params=None): self.ordenes.append(("cancelar", params))
    def fetch_my_trades(self, s, since=None): return self.trades

    def fetch_ohlcv(self, s, tf, limit):
        return [[T0 + i * H, 1, 2, 0.5, 1.5, 10] for i in range(5)]

    def create_order(self, s, tipo, lado, q, precio=None, params=None):
        self.ordenes.append((tipo, lado, q, params or {}))
        return {"average": 0.5, "filled": q}


def test_mercado():
    m = Mercado(CcxtFalso())
    v = m.velas("XRP/USDT:USDT", "1h", 1000, T0 + 4 * H + 60_000)  # la vela 4 todavía no cerró
    assert len(v) == 4
    assert m.limites("XRP/USDT:USDT") == (0.1, 5) and m.ajustar("XRP/USDT:USDT", 12.37) == 12.3


def test_ejecutor_abre_protege_y_cierra():
    cli = CcxtFalso()
    ej = EjecutorBinance(cli, 3)
    precio, q = ej.abrir("XRP/USDT:USDT", -1, 30)
    assert cli.config == ["one-way", "isolated", 3]
    assert cli.ordenes[0] == ("market", "sell", 30, {}) and precio == 0.5
    assert ej.posicion("XRP/USDT:USDT") == {"lado": -1, "cantidad": 30.0, "entrada": 0.5}
    assert ej.proteger("XRP/USDT:USDT", -1, 30, 0.51, 0.48) == []
    assert cli.ordenes[1] == ("market", "buy", 30, {"stopLossPrice": 0.51, "reduceOnly": True})
    assert cli.ordenes[2] == ("market", "buy", 30, {"takeProfitPrice": 0.48, "reduceOnly": True})
    cli.trades = [{"side": "sell", "amount": 30, "price": 0.5, "fee": {"cost": 0.0075, "currency": "USDT"}, "info": {}},
                  {"side": "buy", "amount": 30, "price": 0.48, "fee": {"cost": 0.0072, "currency": "USDT"},
                   "info": {"realizedPnl": "0.6"}}]
    salida, pnl = ej.cerrar("XRP/USDT:USDT", {"lado": -1, "entrada": 0.5, "cantidad": 30, "abierta_ts": 0})
    assert ("market", "buy", 30.0, {"reduceOnly": True}) in cli.ordenes
    assert salida == pytest.approx(0.48) and pnl == pytest.approx(0.6 - 0.0147)
