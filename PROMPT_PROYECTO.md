# Prompt del proyecto Nexaris: fábrica de bots de trading

Copiá todo lo que está debajo de la línea y pegalo en una conversación nueva con una IA para seguir trabajando donde quedamos.

---

## Quién soy y cómo quiero que me ayudes

Soy John, de Uruguay. No sé de trading ni de programación. Explicame todo en español simple, **de a un paso por vez**, esperando mi confirmación (o una foto) antes del paso siguiente. Uso sobre todo el celular. Sé sincero conmigo: no me prometas ganancias seguras.

## Qué es el proyecto

Repositorio GitHub: `johnsosa627-lang/Nexaris` (rama principal `main`). Tiene dos carpetas:

1. **`bot-futuros/`** (primera versión, ya no se usa): bot de Binance Futuros USDT-M con EMA 9/21 + RSI + MACD + Bollinger + volumen, filtro de IA por OpenRouter, protecciones y control por Telegram.
2. **`fabrica/`** (la que está funcionando): una **fábrica de estrategias que se mejora sola**, al estilo StrategyQuant.

## Cómo funciona la fábrica (`fabrica/`)

- **Datos:** Binance Futuros por ccxt. Monedas BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK y LTC. Temporalidades 15m, 1h y 4h. Historia desde 2021-01-01, más el funding. Los **últimos 6 meses se guardan aparte como examen final** y no se usan para crear estrategias.
- **Datos de afuera del gráfico** (se usan como piezas que también se examinan): funding, tendencia de Bitcoin como líder, índice de Miedo y Codicia.
- **Generador:** inventa estrategias al azar y las mejora con un algoritmo genético (mezclar, mutar). Cada estrategia tiene 1 disparador, hasta 2 filtros y reglas de salida (stop, toma de ganancia, stop móvil, salida por tiempo).
  - Disparadores: cruce de medias, precio cruza media, MACD, ruptura Donchian, rebote Bollinger, cruce de RSI, retroceso RSI-2/3, ruptura tras compresión de Bollinger, cambio de Supertrend, ruptura de la nube de Ichimoku y ruptura de consolidación (rango angosto que se rompe) y ruptura de apertura de sesión (ORB de Nueva York 9:30, Londres 8:00 y rango de Asia).
  - Salidas: stop por %, por ATR o por "rango" (debajo del mínimo de las últimas N velas), toma de ganancia, stop móvil, salida por tiempo y salida opcional por señal contraria.
  - Filtros: tendencia, RSI, ADX, volumen, +DI/-DI, funding, tendencia de BTC, miedo/codicia, horario (Asia/Europa/América) y volatilidad (ATR relativo).
- **Estrategias famosas como semillas** (`fabrica/famosas.py`): Tortugas 20 y 55, cruce dorado 50/200, RSI-2 de Connors, MACD + EMA200, Bollinger Squeeze, rebote Bollinger con ADX bajo (estilo Freqtrade), Supertrend 10/3, nube de Ichimoku EMA 8/21 + RSI y 4 variantes de "ruptura de consolidación" (sin filtro, con tendencia, con expansión de ATR, con BTC), con parámetros fijados antes de probar. Entran en cada ciclo y tienen que pasar los mismos exámenes.
- **7 filtros (el colador):**
  1. métricas mínimas;
  2. fuera de muestra + walk-forward;
  3. Monte Carlo de 1000 corridas al 95%;
  4. sobreajuste (mover parámetros un poco);
  5. otras monedas y temporalidades;
  6. entrada tardía;
  7. anti-suerte (precios mezclados) + Deflated Sharpe.
- **Examen final:** se rinde **una sola vez** por estrategia. Las aprobadas van al banco.
- **Revisión con datos nuevos (cada ciclo):** cada estrategia del banco se prueba en las semanas posteriores a su examen. Si con 10+ operaciones pierde plata, queda "vencida" y no entra a la liga. Las que van mejor entran primero.
- **Liga:** hasta 8 **titulares** (los que operan; hasta 2 estrategias distintas por moneda pero una sola posición abierta por moneda; nunca más de 3% de riesgo abierto), con correlación menor a 0,5, y **suplentes** que operan en papel. Ascenso con prueba t ≥ 2 y al menos 30 operaciones. **Jubilación automática** si la caída real supera la del Monte Carlo o si rinde mucho peor que en las pruebas.
- **Modo exploración:** filtros más suaves; esas estrategias se marcan 🧪 y practican en simulado. Solo pueden llegar a plata real si se "gradúan" operando en vivo (30+ operaciones y una prueba estadística t ≥ 2 de que su ganancia no es casualidad), y siempre con el permiso doble.
- **Titulares 🧪 a prueba:** una 🧪 solo sube a titular si practicando como suplente ya gana (5+ operaciones en vivo con promedio de R positivo). Si siendo titular su promedio cae a 0 o menos, vuelve a suplente y sigue practicando; recupera el lugar si mejora (desde el 30/10/2026, después de una semana de pérdidas en la demo).
- **Radar:** calendario económico, volatilidad de BTC, noticias (Cointelegraph, CoinDesk) y Miedo y Codicia. Pausa las entradas si hay peligro y avisa por Telegram.

## Reglas de riesgo (no se tocan)

- 1% de riesgo por operación, máximo 3% en total abierto, apalancamiento máximo 3x.
- Freno diario: −3% en el día, o 2 pérdidas seguidas.
- Freno total: −15% desde el máximo.
- Capital inicial: 100 USD. **Nunca aumentar el capital automáticamente.**
- Plata real **solo** con `MODO=real` + `LIVE_TRADING=true` + confirmación por Telegram (`/confirmar_real`).

## Telegram

- Bot: "Sistema de ganancias".
- Comandos: /estado /hoy /bots /fabrica /ciclo (correr la fábrica ahora) /salud (chequeo automático: datos, ciclos, disco, bots) /diagnostico (¿hubo señales sin operar?) /graduacion (¿cuánto falta para plata real?) /pausar /reanudar /cerrar_todo /informe /radar /ayuda.
- Resumen nocturno a las 22 h (hora de Montevideo). Ciclo semanal de la fábrica: domingo 3:00 UTC.

## Dónde corre

- Servidor VPS de Hostinger (2 núcleos, 8 GB de RAM), con **Easypanel**: proyecto `orangutanjh`, servicio `fabrica` (también hay n8n).
- Fuente en Easypanel: GitHub `johnsosa627-lang/Nexaris`, rama `main`, ruta `/fabrica`, Dockerfile.
- Variables de entorno: solo `TELEGRAM_TOKEN=...`. El chat de Telegram ya viene en `config.yaml`; el modo por defecto es papel.
- Almacenamiento (montaje de volumen): nombre `fabrica-datos`, ruta `/data`.
- **Para actualizar a la última versión** (Easypanel no vuelve a armar la imagen), en la Consola web de Hostinger (hPanel → VPS → Administrador → Consola web):

  ```
  curl -fsSL https://raw.githubusercontent.com/johnsosa627-lang/Nexaris/main/fabrica/actualizar.sh | bash
  ```

  Trabaja solo en segundo plano y avisa por Telegram si salió bien (✅) o mal (❌).
- Consejos: no usar el traductor de Chrome en Easypanel (rompe la página). En Easypanel los nombres van en minúsculas.

## Estado actual (octubre 2026)

- Funciona 24/7 en **modo simulado (papel)** con 100 USD de mentira.
- Se corrigió un error grave: la descarga se cortaba en 1000 velas y ahora baja la historia completa. Por eso los primeros ciclos dieron "Inventó 0 estrategias".
- Tests: 139 pasan (`cd fabrica && python -m pytest -q`).

## Próximos pasos

1. ✅ Hecho (octubre 2026): identidad verificada en Binance, claves de Demo Trading creadas y `MODO=testnet` funcionando (5.000 USDT de práctica en la billetera de Futuros de la demo).
2. Dejar trabajar el sistema varias semanas en la demo y mirar los resúmenes (/bots, /diagnostico, /graduacion).
   - ✅ Hecho el 26/10: (a) la fábrica busca el doble de candidatas en velas de 15 minutos y les pide operar más seguido (300 operaciones/año); (b) hasta 2 titulares por moneda si son distintos, con una sola posición abierta por moneda a la vez. El riesgo por operación sigue en 1%.
3. Solo si gana de forma constante y el examen de graduación está todo en ✅: pasar a plata real con 100 USD, con permiso doble.
4. Opcional, por seguridad: cambiar el token del bot en BotFather y la contraseña de Easypanel (estuvieron visibles en fotos).

## Ideas guardadas para más adelante (no ahora)

- **FTMO / MetaTrader** (opción si lo nuestro no funciona en Binance, o para operar más capital): examen pago, reglas de −5% diario y −10% total (parecidas a nuestros frenos; habría que poner el freno total en −10%), bots en MetaTrader 5 (su conexión con Python necesita Windows) y la fábrica aprendiendo con datos de forex/oro.
- **Piezas nuevas para la fábrica:** interés abierto y liquidaciones de Binance.
- **Salidas parciales:** cerrar la mitad en ganancia y dejar correr el resto.
- **"Te pruebo tu estrategia":** vender por Telegram informes del probador anti-suerte para la estrategia que pida el cliente (sin manejar plata ni claves de nadie; consultar con un contador antes de cobrar).
- **Oro, Nasdaq y acciones:** necesitan años de historia y otro bróker para acciones.
- **Usar a los bots que ganan en vivo como semillas** de la fábrica.

## Reglas para la IA que me ayude

- Nunca publicar tokens, claves ni contraseñas en el código ni en GitHub (el repositorio es público).
- No sacar las protecciones ni bajar la exigencia de los exámenes para que opere más.
- No operar ni mover plata por mí.
- Probar todo con los tests antes de subir cambios.
