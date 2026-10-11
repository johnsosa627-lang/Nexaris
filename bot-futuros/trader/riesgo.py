"""Cálculos puros de riesgo: tamaño, niveles, resultado y límites."""
import math
from typing import Optional, Tuple


def calcular_niveles(lado: str, entrada: float, sl_pct: float, tp_pct: float) -> Tuple[float, float]:
    """Stop-loss y take-profit como % de movimiento del precio."""
    if lado == "LONG":
        return entrada * (1 - sl_pct / 100), entrada * (1 + tp_pct / 100)
    return entrada * (1 + sl_pct / 100), entrada * (1 - tp_pct / 100)


def calcular_pnl(lado: str, entrada: float, salida: float, cantidad: float, comision_pct: float) -> float:
    """Resultado neto en USDT, descontando comisión en la entrada y en la salida."""
    direccion = 1 if lado == "LONG" else -1
    bruto = (salida - entrada) * cantidad * direccion
    comisiones = (entrada * cantidad + salida * cantidad) * comision_pct / 100
    return bruto - comisiones


def calcular_cantidad(saldo: float, fraccion_margen: float, apalancamiento: int, precio: float) -> float:
    """Cantidad (en monedas) usando `fraccion_margen` del saldo como margen."""
    if saldo <= 0 or precio <= 0:
        return 0.0
    return saldo * fraccion_margen * apalancamiento / precio


def redondear_abajo(cantidad: float, paso: Optional[float]) -> float:
    if not paso:
        return cantidad
    pasos = math.floor(cantidad / paso + 1e-9)
    decimales = max(0, -int(math.floor(math.log10(paso)))) if paso < 1 else 0
    return round(pasos * paso, decimales)


def validar_minimos(cantidad: float, precio: float, min_cantidad: Optional[float],
                    min_nocional: Optional[float]) -> Tuple[bool, str]:
    nocional = cantidad * precio
    if cantidad <= 0:
        return False, "La cantidad calculada es 0."
    if min_cantidad and cantidad < min_cantidad:
        return False, f"Cantidad {cantidad} menor al mínimo del par ({min_cantidad})."
    if min_nocional and nocional < min_nocional:
        return False, f"Nocional {nocional:.2f} USDT menor al mínimo del par ({min_nocional} USDT)."
    return True, "ok"


def tocado_sl_tp(lado: str, precio: float, sl: float, tp: float) -> Optional[str]:
    if lado == "LONG":
        if precio <= sl:
            return "SL"
        if precio >= tp:
            return "TP"
    else:
        if precio >= sl:
            return "SL"
        if precio <= tp:
            return "TP"
    return None


def corte_diario_alcanzado(saldo_inicio_dia: float, saldo_actual: float, perdida_max_pct: float) -> bool:
    if saldo_inicio_dia <= 0:
        return False
    return (saldo_inicio_dia - saldo_actual) / saldo_inicio_dia * 100 >= perdida_max_pct
