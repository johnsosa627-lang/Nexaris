# Fábrica de estrategias (en construcción)

Sistema que inventa estrategias de trading, las prueba con precios del pasado, descarta las malas
y las que ganaron por suerte, y pone a operar solo las mejores (primero con plata de mentira).

## En qué etapa estamos

| Etapa | Qué es | Estado |
|---|---|---|
| 1 | Cuentas y claves que tenés que crear | ⏳ falta la verificación de identidad en Binance |
| 2 | Datos + motor de pruebas | ✅ listo |
| 3 | Fábrica de estrategias + filtros + anti-suerte | ✅ listo |
| 4 | Examen final + informes | ✅ listo |
| 5 | Liga de bots en testnet + Telegram + Easypanel | ✅ código listo · falta instalar con tus claves |
| 6 | Pasar a real con el capital de `config.yaml` (100 USDT; solo si lo pedís) | pendiente |

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
- Siempre cobra **comisión** (0,05% por lado), **slippage** (0,02% por lado, más 0,03% extra en los
  stops, que se llenan peor) y **funding** real.
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
python -m fabrica.ciclo --rapido                      # ciclo chico de la fábrica (para probar)
python -m fabrica.ciclo                               # ciclo completo (todas las monedas y temporalidades)
python -m fabrica.examen                              # (re)mostrar el informe del último ciclo
```

La estrategia de ejemplo (cruce de medias) solo sirve para ver que el motor funciona.
No es una recomendación: lo más probable es que pierda, que es justamente lo que la fábrica va a
aprender a descartar.

## Etapa 3: la fábrica

**Cómo se arma una estrategia** (`fabrica/estrategia.py`): siempre es simple.
- 1 **disparador** (el momento de entrar): cruce de medias, precio que cruza su media, cruce del MACD,
  ruptura de máximos (Donchian), rebote en Bollinger o RSI que cruza un nivel.
- 0 a 2 **filtros** (condiciones que tienen que cumplirse): tendencia, RSI, ADX, volumen, +DI/-DI, y
  tres **datos de afuera del gráfico**: el *funding* (si los que apuestan a la suba pagan de más), la
  tendencia de **Bitcoin** (el líder del mercado) y el índice de **Miedo y Codicia**. Pasan por los mismos
  filtros que todo: si de verdad ayudan a decidir, la fábrica los elige; si no, los descarta.
- **Salidas**: stop-loss (siempre) en % o ATR, take-profit, stop móvil, salida por tiempo.
- Puede operar solo compras, solo ventas en corto, o ambas (la venta usa la regla espejo).
- Cada una tiene una explicación en español, por ejemplo: *"Compra cuando el precio supera el máximo
  de las últimas 20 velas, siempre que el volumen sea mayor a 1.5 veces su promedio..."*

**Cómo inventa** (`fabrica/generador.py`): arranca con 200 estrategias al azar y, durante 30
generaciones, cruza las mejores entre sí y las muta (algoritmo genético). Premia ganancia/caída y curva
pareja; castiga las complicadas. Solo usa el 70% más viejo de los datos de trabajo.

**El colador** (`fabrica/filtros.py`): las 30 mejores pasan por 7 filtros, en orden:

1. **Métricas mínimas** (en todo el período de trabajo): ≥200 operaciones, profit factor >1,3,
   ganancia/caída >3, caída máxima <20%, curva pareja >0,8, gana en la mayoría de los años.
2. **Datos no usados + walk-forward**: tiene que ganar en el 30% de datos que no vio, y en un
   walk-forward (elegir con el pasado, probar en el período siguiente) ganar en ≥60% de las ventanas.
3. **Monte Carlo**: 1.000 simulaciones mezclando el orden, salteando 10% de operaciones y con
   comisiones dobles. Tiene que ganar en ≥95%. Guarda la peor caída prevista (para jubilarla en vivo).
4. **Sobreajuste**: 30 variantes moviendo un poco los números; ≥80% tienen que seguir ganando.
5. **Otras monedas y temporalidad vecina**: tiene que ganar en ≥50% de las otras monedas y en la
   temporalidad de al lado.
6. **Entrar una vela tarde**: tiene que seguir ganando.
7. **Anti-suerte**: se corre el MISMO generador sobre precios mezclados al azar (sin ningún patrón real).
   Lo mejor que sale ahí es "lo que da la suerte"; la estrategia tiene que superarlo por 20%.
   Además, el **Deflated Sharpe Ratio** (que corrige por la cantidad de estrategias probadas) tiene que
   ser ≥0,95.

Además, en Monte Carlo la caída del peor 5% de las simulaciones no puede pasar de 25%
(si no, en vivo terminaría chocando con el freno total de la cuenta).

Los resultados de cada ciclo quedan en `resultados/ciclo_FECHA/`: `resumen.txt` (en lenguaje simple),
`embudo.json` (cuántas pasaron cada filtro y por qué se descartó cada una) y `aprobadas/*.json`.

## Etapa 4: examen final e informes

**Examen final** (`fabrica/examen.py`): al terminar cada ciclo, cada estrategia aprobada se prueba
**una sola vez** en los últimos 6 meses, que la fábrica nunca vio. Para aprobar tiene que:
- hacer al menos 10 operaciones,
- ganar plata, con profit factor ≥1,1,
- no caer más de lo que Monte Carlo había previsto como peor caso.

Si reprueba, queda **descartada para siempre**: el resultado queda anotado en `resultados/examenes.json`
y aunque la fábrica la vuelva a inventar en otro ciclo, no se repite ni se reajusta.
Si aprueba, entra al **banco** (`resultados/banco/`), de donde saldrán los suplentes de la liga. En el
banco se guarda también lo que "prometía" el backtest, para comparar en vivo y jubilarla si se aleja.

**Informes** (`fabrica/informes.py`): cada ciclo deja un `informe.txt` en lenguaje simple con el embudo
de filtros, el resultado del examen y una ficha de cada estrategia nueva, por ejemplo:

```
📈 Estrategia 96784cfa4e — XRP, velas de 1 hora
Qué hace: Compra cuando el precio supera el máximo de las últimas 10 velas. Vende en corto en la
situación opuesta. Stop-loss a 3.0% del precio de entrada, toma ganancia a 4.0%, stop móvil a 1.0%.
En el pasado: 1292 operaciones, ganó el 47% de las veces. ...
Lo malo: su peor caída fue de 3.5% y llegó a perder 9 veces seguidas. Eso es normal...
✅ Examen final (meses nunca vistos): APROBÓ. 195 operaciones, resultado +9.3%, peor caída 4.2%.
```
(ejemplo con datos inventados)

**Cuánto tarda**: con 4 núcleos, un ciclo completo (5 monedas × 3 temporalidades) tarda alrededor de
10 a 20 minutos.

**Comprobado con datos inventados**: si se esconde una tendencia real en los precios, la fábrica la
encuentra y la aprueba; si los precios son puro azar, no aprueba nada.

## Etapa 5: la liga de bots, Telegram y el servidor

**La liga** (`fabrica/liga.py`):
- **Titulares** (hasta 3): operan de verdad (en modo testnet, en la cuenta Demo de Binance). Se eligen
  para que no se parezcan entre sí (correlación < 0,5) y uno por moneda.
- **Suplentes** (hasta 12): las estrategias nuevas del banco practican en paralelo, simuladas con los
  precios reales. Siempre simuladas: Binance permite una sola posición por moneda en una cuenta.
- **Ascenso**: un suplente reemplaza a un titular solo si los dos tienen 30+ operaciones en vivo y el
  suplente es claramente mejor (prueba estadística). Una buena racha de pocos días no alcanza.
- **Jubilación automática**: si su caída en vivo supera la peor que había previsto Monte Carlo, o si
  después de 20+ operaciones sus resultados están muy por debajo de lo prometido (prueba estadística).
  Perder varias veces seguidas es normal y NO jubila a nadie.
- Cada bot en vivo usa exactamente las mismas reglas que el motor de pruebas (comprobado con un test que
  compara operación por operación).

**Protección de la cuenta** (`fabrica/cuenta.py`):
- 1% de riesgo por operación y máximo 3% abierto entre todas.
- El riesgo se calcula sobre el capital de `config.yaml` (100 USDT): **las ganancias nunca aumentan
  solas lo que se arriesga**. Para subirlo, lo cambiás vos a mano.
- Freno diario: si pierde 3% en el día o 2 operaciones seguidas, no abre más hasta mañana.
- Freno total: si la cuenta cae 15% desde su máximo, cierra todo, se apaga y te avisa.
- Antes de cada operación verifica el mínimo de Binance; si con el capital no alcanza, no opera y te avisa.
- En testnet, el bot simula una cuenta de 100 USDT aunque la cuenta Demo tenga mucho más saldo.

**Automático** (`fabrica/servicio.py`): actualiza los datos todos los días, revisa ascensos y
jubilaciones todos los días, corre la fábrica todos los domingos (y la primera vez apenas tiene datos),
y te manda un resumen todas las noches a las 22 (hora de Uruguay).

**Telegram** (solo te responde a vos):

| Comando | Qué hace |
|---|---|
| `/estado` | prendido o apagado, cuánta plata hay, si es práctica o real |
| `/hoy` | qué ganó o perdió hoy |
| `/bots` | titulares y suplentes, cómo le va a cada uno |
| `/fabrica` | qué hizo la fábrica en el último ciclo |
| `/informe` | informe semanal |
| `/radar` | qué pasa fuera del mercado (noticias, datos económicos, Bitcoin) |
| `/pausar`, `/reanudar` | dejar de abrir operaciones nuevas / seguir |
| `/cerrar_todo` | cerrar todas las operaciones y pausar |

**Modos** (variable `MODO`):
- `papel`: todo simulado con precios reales. No necesita claves. **Sirve para instalarlo ya.**
- `testnet`: los titulares operan en la cuenta Demo de Binance (plata de mentira).
- `real`: plata real. Necesita `LIVE_TRADING=true` **y** confirmar por Telegram con `/confirmar_real`.

## Radar externo 🛰 (lo que pasa fuera del gráfico)

Las estrategias solo miran el precio. El radar (`fabrica/radar.py`) mira afuera cada 5 minutos y
**protege**: no intenta adivinar el precio, evita entrar en medio del caos.
- **Datos económicos fuertes de EE.UU.** (inflación, Fed, empleo): avisa 1 hora antes y pausa las
  entradas nuevas desde 30 min antes hasta 30 min después.
- **Bitcoin se mueve 3% o más en 15 min**: avisa y pausa las entradas nuevas 1 hora.
- **Noticias graves de cripto** (hackeos, quiebras, retiros frenados): avisa con el link y pausa 1 hora.
- **Noticias importantes** (SEC, ETF, Fed, regulación) y **Miedo y Codicia extremo**: solo avisa.
- Las operaciones abiertas no se tocan (siguen con su stop) y los suplentes siguen practicando.
- Comando `/radar` para ver el estado. Todo se ajusta en `config.yaml`, sección `radar`.

## Modo exploración 🧪 (solo práctica)

Si la fábrica no encuentra nada con los filtros estrictos, igual vas a querer ver bots trabajando.
Con `exploracion.activa: true` en `config.yaml`, además aprueba "en prueba" 🧪 las estrategias que
pasan unos filtros más flojos (también listados ahí). Estas:
- se marcan con 🧪 en Telegram y en los informes,
- entran a la liga solo si sobra lugar después de las estrictas,
- **nunca operan con plata real** (con `MODO=real` quedan siempre como suplentes simuladas).

Con precios puramente al azar, ni siquiera los filtros flojos aprueban nada.

## Instalarlo en Easypanel

1. En Easypanel: tu proyecto → **+ Service** → **App** → nombre `fabrica`.
2. **Source** → GitHub: `johnsosa627-lang` / `Nexaris`, la rama donde está este código,
   **Build Path: `/fabrica`**.
3. **Build** → **Dockerfile**.
4. **Environment** → pegá el contenido de `.env.example` y completá `TELEGRAM_TOKEN` y
   `TELEGRAM_CHAT_ID`. Dejá `MODO=papel` hasta tener las claves de Demo Trading.
5. **Mounts** → **Add Volume**: nombre `fabrica-datos`, Mount Path `/data`.
6. **Deploy**. Te llega "🤖 Fábrica de bots prendida" por Telegram.
7. La primera vez baja toda la historia de Binance y corre el primer ciclo de la fábrica: puede tardar
   entre 30 y 60 minutos. Te avisa cuando termina.
8. Cuando tengas las claves de Demo Trading: cambiá `MODO=testnet`, pegá `BINANCE_API_KEY` y
   `BINANCE_API_SECRET`, y tocá **Deploy** de nuevo. La liga y la historia se conservan (están en el volumen).

También hay un `docker-compose.yml` por si preferís instalarlo como "Compose" (usa el archivo `.env`).

## Configuración

Todos los números están en `config.yaml` (monedas, temporalidades, comisiones, riesgo, filtros).
La carpeta de datos se puede cambiar con la variable `FABRICA_DATOS` (en el servidor va a ser
un volumen persistente).
