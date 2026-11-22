from fabrica import probar_bybit


class CliBybitFalso:
    """Imita lo justo de ccxt/bybit para probar el chequeo sin red (plata de mentira)."""
    def __init__(self):
        self.ordenes = []
    def load_markets(self): return {}
    def market(self, s): return {"limits": {"amount": {"min": 1}, "cost": {"min": 5}}}
    def amount_to_precision(self, s, q): return f"{int(q)}"
    def price_to_precision(self, s, p): return f"{p:.4f}"
    def set_position_mode(self, *a): pass
    def set_margin_mode(self, *a): pass
    def set_leverage(self, *a): pass
    def fetch_balance(self): return {"USDT": {"total": 1000.0}}
    def fetch_ticker(self, s): return {"last": 0.5}
    def fetch_positions(self, s): return [{"symbol": s, "contracts": 12, "side": "long", "entryPrice": 0.5, "info": {}}]
    def fetch_my_trades(self, s, since=None): return []
    def cancel_all_orders(self, s, params=None): pass
    def create_order(self, s, tipo, lado, q, precio=None, params=None):
        self.ordenes.append((tipo, lado, q, params or {}))
        return {"average": 0.5, "filled": q}


def test_main_sin_claves_avisa():
    assert probar_bybit.main([]) == 2  # sin BYBIT_API_KEY/SECRET no hace nada


def test_chequeo_solo_saldo():
    msgs = []
    ok = probar_bybit.probar("k", "s", simbolo=None, log=msgs.append, cliente=CliBybitFalso())
    assert ok and any("1000.00 USDT" in m for m in msgs)


def test_chequeo_con_operacion_abre_y_cierra():
    cli = CliBybitFalso()
    ok = probar_bybit.probar("k", "s", simbolo="XRP/USDT:USDT", log=lambda *_: None, cliente=cli)
    assert ok
    tipos = [o[0] for o in cli.ordenes]
    assert "market" in tipos and len(cli.ordenes) >= 2  # abrió, protegió y cerró


def test_min_cantidad_respeta_el_minimo_por_costo():
    cli = CliBybitFalso()
    # a 0.5 USDT, para llegar al costo mínimo de 5 hacen falta ~10 unidades
    assert probar_bybit._min_cantidad(cli, "XRP/USDT:USDT", 0.5) >= 10
