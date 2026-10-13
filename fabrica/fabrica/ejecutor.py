"""Conexión con Binance Futures USDT-M.

- Mercado: datos públicos (velas, precio, mínimos). Siempre de la cuenta principal, sin claves.
- EjecutorBinance: órdenes de los TITULARES en Demo Trading (testnet) o real. Margen aislado,
  stop-loss y take-profit puestos en el exchange (reduceOnly) y vigilados además por software.
"""
import logging
import time
from typing import Optional, Tuple

import pandas as pd

log = logging.getLogger("fabrica")


def _ccxt():
    import ccxt
    return ccxt


class Mercado:
    def __init__(self, cliente=None):
        self.cliente = cliente or _ccxt().binanceusdm({"enableRateLimit": True})
        self._cargado = False

    def _cargar(self):
        if not self._cargado:
            self.cliente.load_markets()
            self._cargado = True

    def velas(self, simbolo: str, tf: str, limite: int, ahora_ms: int) -> pd.DataFrame:
        from .datos import COLUMNAS, tf_ms
        crudo = self.cliente.fetch_ohlcv(simbolo, tf, limit=min(limite, 1500))
        df = pd.DataFrame(crudo, columns=COLUMNAS)
        df = df[df["ts"] + tf_ms(tf) <= ahora_ms]  # solo velas cerradas
        for c in COLUMNAS[1:]:
            df[c] = df[c].astype(float)
        return df.reset_index(drop=True)

    def precio(self, simbolo: str) -> float:
        t = self.cliente.fetch_ticker(simbolo)
        return float(t.get("last") or t.get("close"))

    def externos_vivo(self, simbolo: str, tf: str, velas: pd.DataFrame, ahora_ms: int, http_get=None) -> dict:
        """Funding, cierre de Bitcoin y Miedo y Codicia alineados con `velas` (los mismos datos que usó la fábrica)."""
        from .datos import SIMBOLO_LIDER, externos_para
        crudo = self.cliente.fetch_funding_rate_history(simbolo, limit=200)
        funding = pd.DataFrame([{"ts": int(x["timestamp"]), "tasa": float(x["fundingRate"])} for x in crudo],
                               columns=["ts", "tasa"])
        lider = velas if simbolo == SIMBOLO_LIDER else self.velas(SIMBOLO_LIDER, tf, len(velas), ahora_ms)
        return externos_para(velas["ts"].to_numpy(), tf, funding, lider, self._miedo_codicia(ahora_ms, http_get))

    def _miedo_codicia(self, ahora_ms: int, http_get=None) -> pd.DataFrame:
        guardado = getattr(self, "_fng", None)
        if guardado is not None and ahora_ms - guardado[0] < 3_600_000:
            return guardado[1]
        import requests
        r = (http_get or requests.get)("https://api.alternative.me/fng/?limit=30&format=json", timeout=15)
        r.raise_for_status()
        df = pd.DataFrame([{"ts": int(x["timestamp"]) * 1000, "valor": float(x["value"])} for x in r.json()["data"]],
                          columns=["ts", "valor"]).sort_values("ts").reset_index(drop=True)
        self._fng = (ahora_ms, df)
        return df

    def limites(self, simbolo: str) -> Tuple[Optional[float], Optional[float]]:
        self._cargar()
        lim = self.cliente.market(simbolo).get("limits", {})
        return (lim.get("amount") or {}).get("min"), (lim.get("cost") or {}).get("min")

    def ajustar(self, simbolo: str, cantidad: float) -> float:
        self._cargar()
        try:
            return float(self.cliente.amount_to_precision(simbolo, cantidad))
        except Exception:  # noqa: BLE001 - por debajo de la precisión mínima
            return 0.0


def crear_cliente_privado(modo: str, api_key: str, secret: str):
    cliente = _ccxt().binanceusdm({"apiKey": api_key, "secret": secret, "enableRateLimit": True,
                                   "options": {"adjustForTimeDifference": True}})
    if modo == "testnet":
        cliente.enable_demo_trading(True)  # Binance reemplazó el testnet de futuros por "Demo Trading"
    return cliente


def _lado_orden(lado: int, cerrar: bool = False) -> str:
    compra = lado == 1
    if cerrar:
        compra = not compra
    return "buy" if compra else "sell"


class EjecutorBinance:
    def __init__(self, cliente, apalancamiento: int = 3, comision_pct: float = 0.05):
        self.cliente = cliente
        self.apalancamiento = apalancamiento
        self.comision = comision_pct / 100
        self._preparados = set()

    def preparar(self, simbolo: str):
        if simbolo in self._preparados:
            return
        if not self._preparados:
            self.cliente.load_markets()
            try:
                self.cliente.set_position_mode(False)  # una sola posición neta por moneda
            except Exception as e:  # noqa: BLE001
                log.info("Modo de posición: %s", e)
        try:
            self.cliente.set_margin_mode("isolated", simbolo)
        except Exception as e:  # noqa: BLE001 - "No need to change margin type" es normal
            log.info("Margen aislado %s: %s", simbolo, e)
        self.cliente.set_leverage(self.apalancamiento, simbolo)
        self._preparados.add(simbolo)

    def saldo(self) -> float:
        b = self.cliente.fetch_balance()
        for a in (b.get("info") or {}).get("assets", []) or []:
            if a.get("asset") == "USDT" and a.get("walletBalance") is not None:
                return float(a["walletBalance"])
        return float((b.get("USDT") or {}).get("total") or 0.0)

    def precio(self, simbolo: str) -> float:
        t = self.cliente.fetch_ticker(simbolo)
        return float(t.get("last") or t.get("close"))

    def posicion(self, simbolo: str) -> Optional[dict]:
        for p in self.cliente.fetch_positions([simbolo]):
            if p.get("symbol") != simbolo:
                continue
            cantidad = abs(float(p.get("contracts") or 0))
            if cantidad > 0:
                lado = p.get("side")
                if lado not in ("long", "short"):
                    lado = "long" if float((p.get("info") or {}).get("positionAmt", 0)) > 0 else "short"
                return {"lado": 1 if lado == "long" else -1, "cantidad": cantidad, "entrada": float(p.get("entryPrice"))}
        return None

    def abrir(self, simbolo: str, lado: int, cantidad: float) -> Tuple[float, float]:
        self.preparar(simbolo)
        orden = self.cliente.create_order(simbolo, "market", _lado_orden(lado), cantidad)
        precio, ejecutada = orden.get("average"), orden.get("filled") or cantidad
        if not precio:
            time.sleep(1)
            pos = self.posicion(simbolo)
            precio, ejecutada = (pos["entrada"], pos["cantidad"]) if pos else (self.precio(simbolo), cantidad)
        return float(precio), float(ejecutada)

    def _precio_ok(self, simbolo, precio):
        try:
            return float(self.cliente.price_to_precision(simbolo, precio))
        except Exception:  # noqa: BLE001
            return precio

    def proteger(self, simbolo: str, lado: int, cantidad: float, stop: float, tp: Optional[float]) -> list:
        """Pone stop-loss (y take-profit si hay) en el exchange. Devuelve la lista de errores."""
        errores = []
        ordenes = [("stop-loss", {"stopLossPrice": self._precio_ok(simbolo, stop)})]
        if tp is not None:
            ordenes.append(("take-profit", {"takeProfitPrice": self._precio_ok(simbolo, tp)}))
        for nombre, extra in ordenes:
            try:
                self.cliente.create_order(simbolo, "market", _lado_orden(lado, cerrar=True), cantidad, None,
                                          {**extra, "reduceOnly": True})
            except Exception as e:  # noqa: BLE001
                log.error("No se pudo poner el %s en %s: %s", nombre, simbolo, e)
                errores.append(f"{nombre}: {e}")
        return errores

    def cancelar_protecciones(self, simbolo: str):
        for params in ({"trigger": True}, {}):
            try:
                self.cliente.cancel_all_orders(simbolo, params)
            except Exception as e:  # noqa: BLE001
                log.info("Cancelar órdenes %s %s: %s", simbolo, params, e)

    def mover_stop(self, simbolo: str, lado: int, cantidad: float, stop: float, tp: Optional[float]) -> list:
        self.cancelar_protecciones(simbolo)
        return self.proteger(simbolo, lado, cantidad, stop, tp)

    def cerrar(self, simbolo: str, pos: dict) -> Tuple[float, float]:
        actual = self.posicion(simbolo)
        precio_orden = None
        if actual:
            orden = self.cliente.create_order(simbolo, "market", _lado_orden(actual["lado"], cerrar=True),
                                              actual["cantidad"], None, {"reduceOnly": True})
            precio_orden = orden.get("average")
        self.cancelar_protecciones(simbolo)
        return self.resultado_cierre(simbolo, pos, precio_orden)

    def resultado_cierre(self, simbolo: str, pos: dict, precio_estimado: Optional[float] = None) -> Tuple[float, float]:
        """Precio de salida y resultado en USDT, leídos de las operaciones reales del exchange."""
        self.cancelar_protecciones(simbolo)
        desde = int(pos.get("abierta_ts", 0)) - 5_000
        for intento in range(3):
            try:
                trades = self.cliente.fetch_my_trades(simbolo, since=desde)
            except Exception as e:  # noqa: BLE001
                log.warning("No se pudieron leer los trades de %s: %s", simbolo, e)
                break
            cierres = [t for t in trades if t.get("side") == _lado_orden(pos["lado"], cerrar=True)]
            if cierres:
                cantidad = sum(float(t["amount"]) for t in cierres)
                salida = sum(float(t["price"]) * float(t["amount"]) for t in cierres) / cantidad
                realizado = sum(float((t.get("info") or {}).get("realizedPnl", 0) or 0) for t in cierres)
                comisiones = sum(float((t.get("fee") or {}).get("cost") or 0) for t in trades
                                 if (t.get("fee") or {}).get("currency") in (None, "USDT"))
                return salida, realizado - comisiones
            time.sleep(1 + intento)
        salida = float(precio_estimado or self.precio(simbolo))
        pnl = pos["lado"] * (salida - pos["entrada"]) * pos["cantidad"] - self.comision * (pos["entrada"] + salida) * pos["cantidad"]
        return salida, pnl
