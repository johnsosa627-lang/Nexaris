"""Estrategias públicas y conocidas, armadas con las piezas de la fábrica.

Entran en la población inicial de CADA ciclo: la fábrica las prueba, las mezcla y las muta como a
cualquier otra, y tienen que pasar los mismos filtros y el examen final. Ser famosa no es aprobar.
"""
import copy


def _s(stop_tipo, stop, tp_tipo="ninguno", tp=0.0, trailing=0.0, max_velas=0, contraria=False):
    s = {"stop_tipo": stop_tipo, "stop": stop, "tp_tipo": tp_tipo, "tp": tp, "trailing": trailing, "max_velas": max_velas}
    if contraria:
        s["salida_contraria"] = True
    return s


FAMOSAS = [
    {"famosa": "Tortugas, sistema 1 (Richard Dennis, años 80)", "lado": "ambos",
     "reglas": [{"tipo": "ruptura_donchian", "n": 20}], "salidas": _s("atr", 2.0, trailing=3.0)},
    {"famosa": "Tortugas, sistema 2 (ruptura de 55)", "lado": "ambos",
     "reglas": [{"tipo": "ruptura_donchian", "n": 55}], "salidas": _s("atr", 2.0, trailing=4.0)},
    {"famosa": "Cruce dorado (media 50 sobre media 200)", "lado": "ambos",
     "reglas": [{"tipo": "cruce_medias", "media": "sma", "rapida": 50, "lenta": 200}], "salidas": _s("atr", 3.0, trailing=4.0)},
    {"famosa": "RSI-2 de Larry Connors (compra retrocesos en tendencia alcista)", "lado": "long",
     "reglas": [{"tipo": "retroceso_rsi", "n": 2, "nivel": 10}, {"tipo": "tendencia", "media": "sma", "n": 200}],
     "salidas": _s("atr", 3.0, "atr", 1.5, max_velas=12)},
    {"famosa": "MACD con filtro de media 200", "lado": "ambos",
     "reglas": [{"tipo": "cruce_macd", "rapida": 12, "lenta": 26, "senal": 9}, {"tipo": "tendencia", "media": "ema", "n": 200}],
     "salidas": _s("atr", 2.0, "atr", 3.0)},
    {"famosa": "Bollinger Squeeze (John Bollinger)", "lado": "ambos",
     "reglas": [{"tipo": "ruptura_compresion", "n": 20, "m": 100}, {"tipo": "volumen_filtro", "mult": 1.5}],
     "salidas": _s("atr", 2.0, trailing=3.0)},
    {"famosa": "Rebote en Bollinger con mercado lateral (estilo Freqtrade BinHV45)", "lado": "long",
     "reglas": [{"tipo": "rebote_bollinger", "n": 20, "k": 2.0}, {"tipo": "adx_filtro", "op": "<", "nivel": 20}],
     "salidas": _s("atr", 2.0, "atr", 2.0, max_velas=48)},
    {"famosa": "Supertrend (10, 3)", "lado": "ambos",
     "reglas": [{"tipo": "cambio_supertrend", "n": 10, "k": 3.0}], "salidas": _s("atr", 3.0, trailing=3.0)},
    {"famosa": "Ruptura de la nube de Ichimoku", "lado": "ambos",
     "reglas": [{"tipo": "ruptura_nube", "t": 9, "k": 26, "s": 52}, {"tipo": "adx_filtro", "op": ">", "nivel": 20}],
     "salidas": _s("atr", 2.5, trailing=3.0)},
    {"famosa": "Cruce de medias rápidas 8/21 con RSI y volumen", "lado": "ambos",
     "reglas": [{"tipo": "cruce_medias", "media": "ema", "rapida": 8, "lenta": 21},
                {"tipo": "rsi_filtro", "n": 14, "op": ">", "nivel": 50}],
     "salidas": _s("atr", 1.5, "atr", 3.0)},
    # Familia "ruptura de consolidación" (parámetros fijados ANTES de probar, sin mirar resultados ni el examen):
    # rango de 20 velas con alto menor a 4 ATR; stop debajo del rango; stop móvil de 3 ATR; salida por tiempo
    # si la ruptura no avanza en 48 velas. Variantes: sin filtro, con tendencia, con expansión de ATR, con BTC.
    {"famosa": "Ruptura de consolidación (sin filtros)", "lado": "ambos",
     "reglas": [{"tipo": "ruptura_rango", "n": 20, "ancho": 4.0}],
     "salidas": _s("rango", 20, trailing=3.0, max_velas=48)},
    {"famosa": "Ruptura de consolidación con tendencia (media 200)", "lado": "ambos",
     "reglas": [{"tipo": "ruptura_rango", "n": 20, "ancho": 4.0}, {"tipo": "tendencia", "media": "ema", "n": 200}],
     "salidas": _s("rango", 20, trailing=3.0, max_velas=48)},
    {"famosa": "Ruptura de consolidación con expansión de volatilidad", "lado": "ambos",
     "reglas": [{"tipo": "ruptura_rango", "n": 20, "ancho": 4.0}, {"tipo": "volatilidad", "op": ">", "nivel": 1.0}],
     "salidas": _s("rango", 20, trailing=3.0, max_velas=48)},
    {"famosa": "Ruptura de consolidación a favor de Bitcoin, con salida por señal contraria", "lado": "ambos",
     "reglas": [{"tipo": "ruptura_rango", "n": 20, "ancho": 4.0}, {"tipo": "btc_tendencia", "n": 100}],
     "salidas": _s("rango", 20, trailing=3.0, max_velas=48, contraria=True)},
]


def famosas() -> list:
    return copy.deepcopy(FAMOSAS)
