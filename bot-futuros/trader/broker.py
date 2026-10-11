"""Acceso al exchange: simulado (papel) o Binance USDT-M (testnet demo / real)."""
import logging
import time
from typing import Optional, Tuple

import ccxt

from .riesgo import calcular_pnl

log = logging.getLogger("trader")


def crear_cliente(cfg):
    opciones = {
        "enableRateLimit": True,
        "options": {"defaultType": "future", "adjustForTimeDifference": True},
    }
    if cfg.modo in ("testnet", "real"):
        opciones["apiKey"] = cfg.binance_api_key
        opciones["secret"] = cfg.binance_api_secret
    cliente = ccxt.binanceusdm(opciones)
    if cfg.modo == "testnet":
        # Binance reemplazó el viejo testnet de futuros por "Demo Trading"
        cliente.enable_demo_trading(True)
    return cliente


def lado_cierre(lado: str) -> str:
    return "sell" if lado == "LONG" else "buy"


def lado_apertura(lado: str) -> str:
    return "buy" if lado == "LONG" else "sell"


class BrokerBase:
    """Datos de mercado comunes a todos los modos."""

    def __init__(self, cfg, cliente):
        self.cfg = cfg
        self.cliente = cliente
        self.simbolo = cfg.simbolo
        self.min_cantidad: Optional[float] = None
        self.min_nocional: Optional[float] = None

    def cargar_mercado(self):
        self.cliente.load_markets()
        mercado = self.cliente.market(self.simbolo)
        limites = mercado.get("limits", {})
        self.min_cantidad = (limites.get("amount") or {}).get("min")
        self.min_nocional = (limites.get("cost") or {}).get("min")
        log.info("Mercado %s: cantidad mínima=%s, nocional mínimo=%s",
                 self.simbolo, self.min_cantidad, self.min_nocional)

    def velas(self, limite: int = 250) -> list:
        return self.cliente.fetch_ohlcv(self.simbolo, self.cfg.timeframe, limit=limite)

    def precio(self) -> float:
        ticker = self.cliente.fetch_ticker(self.simbolo)
        return float(ticker.get("last") or ticker.get("close"))

    def ajustar_cantidad(self, cantidad: float) -> float:
        """Trunca la cantidad al paso permitido por el par."""
        try:
            return float(self.cliente.amount_to_precision(self.simbolo, cantidad))
        except Exception:  # noqa: BLE001 - por debajo de la precisión mínima
            return 0.0

    def ajustar_precio(self, precio: float) -> float:
        try:
            return float(self.cliente.price_to_precision(self.simbolo, precio))
        except Exception:  # noqa: BLE001
            return precio


class BrokerPapel(BrokerBase):
    """Datos reales de Binance, operaciones simuladas con saldo virtual."""

    modo = "papel"

    def __init__(self, cfg, cliente, estado):
        super().__init__(cfg, cliente)
        self.estado = estado
        papel = dict(estado["papel"])
        if papel.get("saldo") is None:
            papel["saldo"] = cfg.saldo_inicial_papel
            estado["papel"] = papel

    def preparar(self):
        log.info("Modo papel: saldo virtual %.4f USDT", self.saldo())

    def saldo(self) -> float:
        return float(self.estado["papel"]["saldo"])

    def posicion(self) -> Optional[dict]:
        return self.estado["papel"].get("posicion")

    def abrir(self, lado: str, cantidad: float) -> Tuple[float, float]:
        entrada = self.precio()
        papel = dict(self.estado["papel"])
        papel["posicion"] = {"lado": lado, "cantidad": cantidad, "entrada": entrada}
        self.estado["papel"] = papel
        return entrada, cantidad

    def colocar_protecciones(self, lado, cantidad, sl, tp) -> list:
        return []  # en papel el SL/TP lo vigila el software

    def cancelar_protecciones(self):
        pass

    def cerrar(self, pos: dict) -> Tuple[float, float]:
        salida = self.precio()
        return salida, self._liquidar(pos, salida)

    def cierre_externo(self, pos: dict) -> Tuple[float, float]:
        return self.cerrar(pos)

    def _liquidar(self, pos: dict, salida: float) -> float:
        pnl = calcular_pnl(pos["lado"], pos["entrada"], salida, pos["cantidad"], self.cfg.comision_pct)
        papel = dict(self.estado["papel"])
        papel["saldo"] = float(papel["saldo"]) + pnl
        papel["posicion"] = None
        self.estado["papel"] = papel
        return pnl


class BrokerBinance(BrokerBase):
    """Órdenes reales en Binance USDT-M (cuenta demo o real)."""

    def __init__(self, cfg, cliente):
        super().__init__(cfg, cliente)
        self.modo = cfg.modo

    def preparar(self):
        try:
            self.cliente.set_position_mode(False, self.simbolo)  # modo one-way
        except Exception as e:  # noqa: BLE001
            log.info("Modo de posición: %s", e)
        try:
            self.cliente.set_margin_mode("isolated", self.simbolo)
        except Exception as e:  # noqa: BLE001 - "No need to change margin type" es normal
            log.info("Margen aislado: %s", e)
        self.cliente.set_leverage(self.cfg.apalancamiento, self.simbolo)
        log.info("Apalancamiento %sx, margen aislado en %s", self.cfg.apalancamiento, self.simbolo)

    def saldo(self) -> float:
        balance = self.cliente.fetch_balance()
        for activo in (balance.get("info") or {}).get("assets", []) or []:
            if activo.get("asset") == "USDT" and activo.get("walletBalance") is not None:
                return float(activo["walletBalance"])
        return float((balance.get("USDT") or {}).get("total") or 0.0)

    def posicion(self) -> Optional[dict]:
        for p in self.cliente.fetch_positions([self.simbolo]):
            if p.get("symbol") != self.simbolo:
                continue
            contratos = abs(float(p.get("contracts") or 0))
            if contratos <= 0:
                continue
            lado = p.get("side")
            if lado not in ("long", "short"):
                lado = "long" if float((p.get("info") or {}).get("positionAmt", 0)) > 0 else "short"
            return {"lado": lado.upper(), "cantidad": contratos, "entrada": float(p.get("entryPrice"))}
        return None

    def abrir(self, lado: str, cantidad: float) -> Tuple[float, float]:
        orden = self.cliente.create_order(self.simbolo, "market", lado_apertura(lado), cantidad)
        entrada = orden.get("average") or None
        ejecutada = orden.get("filled") or cantidad
        if not entrada:
            time.sleep(1)
            pos = self.posicion()
            if pos:
                entrada, ejecutada = pos["entrada"], pos["cantidad"]
        return float(entrada or self.precio()), float(ejecutada)

    def colocar_protecciones(self, lado, cantidad, sl, tp) -> list:
        errores = []
        cierre = lado_cierre(lado)
        for nombre, extra in (("stop-loss", {"stopLossPrice": self.ajustar_precio(sl)}),
                              ("take-profit", {"takeProfitPrice": self.ajustar_precio(tp)})):
            try:
                self.cliente.create_order(self.simbolo, "market", cierre, cantidad, None,
                                          {**extra, "reduceOnly": True})
            except Exception as e:  # noqa: BLE001
                log.error("No se pudo colocar el %s: %s", nombre, e)
                errores.append(f"{nombre}: {e}")
        return errores

    def cancelar_protecciones(self):
        for params in ({"trigger": True}, {}):
            try:
                self.cliente.cancel_all_orders(self.simbolo, params)
            except Exception as e:  # noqa: BLE001
                log.info("Cancelar órdenes %s: %s", params, e)

    def cerrar(self, pos: dict) -> Tuple[float, float]:
        actual = self.posicion()
        if actual:
            orden = self.cliente.create_order(self.simbolo, "market", lado_cierre(actual["lado"]),
                                              actual["cantidad"], None, {"reduceOnly": True})
            salida_orden = orden.get("average")
        else:
            salida_orden = None
        self.cancelar_protecciones()
        resultado = self._resultado_desde_trades(pos)
        if resultado:
            return resultado
        salida = float(salida_orden or self.precio())
        return salida, calcular_pnl(pos["lado"], pos["entrada"], salida, pos["cantidad"], self.cfg.comision_pct)

    def cierre_externo(self, pos: dict) -> Tuple[float, float]:
        """La posición se cerró sola (SL/TP del exchange o manual)."""
        self.cancelar_protecciones()
        resultado = self._resultado_desde_trades(pos)
        if resultado:
            return resultado
        precio = self.precio()
        salida = min((pos["sl"], pos["tp"]), key=lambda nivel: abs(nivel - precio))
        return salida, calcular_pnl(pos["lado"], pos["entrada"], salida, pos["cantidad"], self.cfg.comision_pct)

    def _resultado_desde_trades(self, pos: dict) -> Optional[Tuple[float, float]]:
        desde = int(pos.get("abierta_ts", 0)) - 5_000
        for intento in range(3):
            try:
                trades = self.cliente.fetch_my_trades(self.simbolo, since=desde)
            except Exception as e:  # noqa: BLE001
                log.warning("No se pudieron leer los trades: %s", e)
                return None
            cierres = [t for t in trades if t.get("side") == lado_cierre(pos["lado"])]
            if cierres:
                cantidad = sum(float(t["amount"]) for t in cierres)
                salida = sum(float(t["price"]) * float(t["amount"]) for t in cierres) / cantidad
                realizado = sum(float((t.get("info") or {}).get("realizedPnl", 0) or 0) for t in cierres)
                comisiones = sum(float((t.get("fee") or {}).get("cost") or 0) for t in trades
                                 if (t.get("fee") or {}).get("currency") in (None, "USDT"))
                return salida, realizado - comisiones
            time.sleep(1 + intento)
        return None
