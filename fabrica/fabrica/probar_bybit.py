"""Prueba manual de la conexión con Bybit (cuenta DEMO), para preparar el fondeo.

Es un chequeo de UNA sola vez: se conecta, mira el saldo y los datos del mercado, y —si se pide—
abre una posición mínima, le pone el stop y la cierra. Sirve para confirmar que nuestro ejecutor
de Bybit funciona de verdad ANTES de depender de él en un examen.

NO toca Binance ni el sistema que está corriendo (es un proceso aparte que arranca y termina).
Siempre sobre la cuenta DEMO de Bybit (plata de mentira).

Uso (con las claves de la DEMO de Bybit en el entorno):
    BYBIT_API_KEY=... BYBIT_API_SECRET=... python -m fabrica.probar_bybit
    # además prueba una operación mínima (abrir, stop y cerrar):
    BYBIT_API_KEY=... BYBIT_API_SECRET=... python -m fabrica.probar_bybit --orden XRP/USDT:USDT
"""
import os
import sys
import time

from .ejecutor import EjecutorBybit, crear_cliente_bybit


def _min_cantidad(cliente, simbolo: str, precio: float) -> float:
    """Cantidad mínima que acepta Bybit para ese símbolo (por cantidad y por costo en USDT)."""
    lim = cliente.market(simbolo).get("limits", {})
    min_amount = (lim.get("amount") or {}).get("min") or 0.0
    min_costo = (lim.get("cost") or {}).get("min") or 5.0
    por_costo = (min_costo / precio) if precio else 0.0
    cruda = max(float(min_amount), por_costo) * 1.05  # un pelín arriba del mínimo
    return float(cliente.amount_to_precision(simbolo, cruda))


def probar(clave: str, secreto: str, simbolo: str = None, log=print, cliente=None) -> bool:
    """Hace el chequeo. Devuelve True si salió todo bien. `simbolo` != None también prueba una operación.

    `cliente` se puede pasar ya hecho (para pruebas); si no, se crea el de la demo de Bybit.
    """
    log("🔌 Conectando a la DEMO de Bybit...")
    cliente = cliente or crear_cliente_bybit("demo", clave, secreto)
    cliente.load_markets()
    ej = EjecutorBybit(cliente, apalancamiento=3)

    saldo = ej.saldo()
    log(f"💰 Saldo en la demo de Bybit: {saldo:.2f} USDT")

    if not simbolo:
        log("✅ Conexión y saldo OK. (No probé ninguna operación; para eso usá --orden <SIMBOLO>.)")
        return True

    precio = ej.precio(simbolo)
    cantidad = _min_cantidad(cliente, simbolo, precio)
    log(f"📈 {simbolo}: precio {precio:.6g} · cantidad mínima a probar {cantidad:g}")
    if cantidad <= 0:
        log("⚠️ No pude calcular una cantidad válida; corto acá sin operar.")
        return False

    log("🟢 Abriendo una compra mínima...")
    entrada, ejecutada = ej.abrir(simbolo, 1, cantidad)
    log(f"   Entró a {entrada:.6g} por {ejecutada:g}")

    stop = entrada * 0.95  # stop lejos: es solo para probar que se pone, no para que salte
    errores = ej.proteger(simbolo, 1, ejecutada, stop, None)
    log("   Stop puesto ✅" if not errores else f"   Problema al poner el stop: {errores}")

    time.sleep(1)
    log("🔴 Cerrando la posición de prueba...")
    salida, pnl = ej.cerrar(simbolo, {"lado": 1, "entrada": entrada, "cantidad": ejecutada, "abierta_ts": 0})
    log(f"   Cerró a {salida:.6g} · resultado {pnl:+.4f} USDT (es plata de mentira)")
    ok = not errores
    log("✅ Prueba completa: el ejecutor de Bybit funciona." if ok else "⚠️ Terminó con avisos, revisá arriba.")
    return ok


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    clave, secreto = os.getenv("BYBIT_API_KEY", "").strip(), os.getenv("BYBIT_API_SECRET", "").strip()
    if not (clave and secreto):
        print("Faltan las claves de la DEMO de Bybit. Poné BYBIT_API_KEY y BYBIT_API_SECRET en el entorno.")
        return 2
    simbolo = None
    if "--orden" in argv:
        i = argv.index("--orden")
        simbolo = argv[i + 1] if i + 1 < len(argv) else "XRP/USDT:USDT"
    try:
        return 0 if probar(clave, secreto, simbolo) else 1
    except Exception as e:  # noqa: BLE001 - es una herramienta manual: mostrar el error claro
        print(f"❌ Falló la prueba de Bybit: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
