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

- **Datos:** Binance Futuros por ccxt. Monedas BTC, ETH, SOL, BNB y XRP. Temporalidades 15m, 1h y 4h. Historia desde 2021-01-01, más el funding. Los **últimos 6 meses se guardan aparte como examen final** y no se usan para crear estrategias.
- **Datos de afuera del gráfico** (se usan como piezas que también se examinan): funding, tendencia de Bitcoin como líder, índice de Miedo y Codicia.
- **Generador:** inventa estrategias al azar y las mejora con un algoritmo genético (mezclar, mutar). Cada estrategia tiene 1 disparador, hasta 2 filtros y reglas de salida (stop, toma de ganancia, stop móvil, salida por tiempo).
  - Disparadores: cruce de medias, precio cruza media, MACD, ruptura Donchian, rebote Bollinger, cruce de RSI, retroceso RSI-2/3, ruptura tras compresión de Bollinger, cambio de Supertrend, ruptura de la nube de Ichimoku y ruptura de consolidación (rango angosto que se rompe).
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
- **Liga:** de 3 a 5 **titulares** (los que operan), con correlación menor a 0,5, y **suplentes** que operan en papel. Ascenso con prueba t ≥ 2 y al menos 30 operaciones. **Jubilación automática** si la caída real supera la del Monte Carlo o si rinde mucho peor que en las pruebas.
- **Modo exploración:** filtros más suaves; esas estrategias se marcan 🧪 y nunca operan con plata real.
- **Radar:** calendario económico, volatilidad de BTC, noticias (Cointelegraph, CoinDesk) y Miedo y Codicia. Pausa las entradas si hay peligro y avisa por Telegram.

## Reglas de riesgo (no se tocan)

- 1% de riesgo por operación, máximo 3% en total abierto, apalancamiento máximo 3x.
- Freno diario: −3% en el día, o 2 pérdidas seguidas.
- Freno total: −15% desde el máximo.
- Capital inicial: 100 USD. **Nunca aumentar el capital automáticamente.**
- Plata real **solo** con `MODO=real` + `LIVE_TRADING=true` + confirmación por Telegram (`/confirmar_real`).

## Telegram

- Bot: "Sistema de ganancias".
- Comandos: /estado /hoy /bots /fabrica /ciclo (correr la fábrica ahora) /salud (chequeo automático: datos, ciclos, disco) /pausar /reanudar /cerrar_todo /informe /radar /ayuda.
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
- Tests: 112 pasan (`cd fabrica && python -m pytest -q`).

## Próximos pasos

1. Dejar trabajar la fábrica 1 o 2 meses en simulado y mirar los resúmenes.
2. Cuando Binance verifique mi identidad: crear claves de Demo Trading y pasar a `MODO=testnet`.
3. Solo si gana de forma constante: pasar a plata real con 100 USD, con permiso doble.
4. Opcional, por seguridad: cambiar el token del bot en BotFather (estuvo visible en fotos) y actualizarlo en Easypanel.

## Reglas para la IA que me ayude

- Nunca publicar tokens, claves ni contraseñas en el código ni en GitHub (el repositorio es público).
- No sacar las protecciones ni bajar la exigencia de los exámenes para que opere más.
- No operar ni mover plata por mí.
- Probar todo con los tests antes de subir cambios.
