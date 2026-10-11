# Fábrica de estrategias (en construcción)

Sistema que inventa estrategias de trading, las prueba con precios del pasado, descarta las malas
y las que ganaron por suerte, y pone a operar solo las mejores (primero con plata de mentira).

## En qué etapa estamos

| Etapa | Qué es | Estado |
|---|---|---|
| 1 | Cuentas y claves que tenés que crear | ⏳ falta la verificación de identidad en Binance |
| 2 | Datos + motor de pruebas | ✅ listo |
| 3 | Fábrica de estrategias + filtros + anti-suerte | pendiente |
| 4 | Examen final + informes | pendiente |
| 5 | Liga de bots en testnet + Telegram + Easypanel | pendiente |
| 6 | Pasar a real con 15 dólares (solo si lo pedís) | pendiente |

## Etapa 2: qué hace

**Datos** (`fabrica/datos.py`)
- Baja de Binance Futures las velas de BTC, ETH, SOL, BNB y XRP en 15m, 1h y 4h, más el historial
  de *funding* (el cobro o pago cada 8 horas por tener una posición abierta). No necesita claves.
- La primera vez baja toda la historia desde la fecha de `config.yaml`; después solo lo que falta.
- Revisa que no haya velas faltantes, repetidas o con precios imposibles.
- Separa los **últimos 6 meses como examen final**: la fábrica nunca los usa para crear estrategias.

**Motor de pruebas** (`fabrica/motor.py`)
- Simula una estrategia vela por vela, sin mirar el futuro: decide al cierre de una vela y entra
  en la apertura de la siguiente.
- Siempre cobra **comisión** (0,05% por lado), **slippage** (0,02% por lado) y **funding** real.
- Toda operación tiene stop-loss; si no lo tiene, el motor se niega a correr.
- Si en una vela se tocan el stop y el take-profit, cuenta como pérdida (lo más prudente).
- Si el precio "salta" por encima del stop, cobra el precio real del salto, no el del stop.
- Tamaño de cada operación: arriesga el 1% del capital, con apalancamiento máximo 3x.
- Salidas: stop y take-profit en % o en ATR, stop móvil, salida por tiempo y por señal.
- Puede simular "entrar una vela tarde" (se usa en los filtros de la etapa 3).
- Rápido: unas 140.000 velas (4 años de 15m) en menos de medio segundo.

**Métricas** (`fabrica/metricas.py`): cantidad de operaciones, % ganadoras, profit factor,
retorno, peor caída (drawdown), ganancia/caída (Ret/DD), qué tan pareja es la curva (estabilidad),
Sharpe, peor racha, resultado por año, y un resumen en lenguaje simple.

## Comandos

```bash
cd fabrica
pip install -r requirements-dev.txt

python -m pytest -q                                   # pruebas automáticas
python -m fabrica.datos actualizar                    # bajar/actualizar datos de Binance
python -m fabrica.datos revisar                       # controlar calidad de los datos
python -m fabrica.ejemplo --simbolo XRP/USDT:USDT --tf 1h   # probar el motor con una estrategia de ejemplo
```

La estrategia de ejemplo (cruce de medias) solo sirve para ver que el motor funciona.
No es una recomendación: lo más probable es que pierda, que es justamente lo que la fábrica va a
aprender a descartar.

## Configuración

Todos los números están en `config.yaml` (monedas, temporalidades, comisiones, riesgo, filtros).
La carpeta de datos se puede cambiar con la variable `FABRICA_DATOS` (en el servidor va a ser
un volumen persistente).
