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

- **Datos:** Binance Futuros por ccxt. Monedas BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK, LTC, TRX, DOT, NEAR, ATOM y BCH (las 5 últimas desde el 18/11/2026). Temporalidades 15m, 1h y 4h. Historia desde 2021-01-01, más el funding. Los **últimos 6 meses se guardan aparte como examen final** y no se usan para crear estrategias.
- **Datos de afuera del gráfico** (se usan como piezas que también se examinan): funding, tendencia de Bitcoin como líder, índice de Miedo y Codicia.
- **Generador:** inventa estrategias al azar y las mejora con un algoritmo genético (mezclar, mutar). Cada estrategia tiene 1 disparador, hasta 2 filtros y reglas de salida (stop, toma de ganancia, stop móvil, salida por tiempo).
  - Disparadores: cruce de medias, precio cruza media, MACD, ruptura Donchian, rebote Bollinger, cruce de RSI, retroceso RSI-2/3, ruptura tras compresión de Bollinger, cambio de Supertrend, ruptura de la nube de Ichimoku y ruptura de consolidación (rango angosto que se rompe) y ruptura de apertura de sesión (ORB de Nueva York 9:30, Londres 8:00 y rango de Asia), Turtle Soup (falsa ruptura, Linda Raschke), cierre extremo de n velas (Double 7s, Larry Connors), ruptura del canal de Keltner, cruce del estocástico en sobreventa, ruptura de vela interior (price action) y cruce del VWAP del día.
  - Salidas: stop por %, por ATR o por "rango" (debajo del mínimo de las últimas N velas), toma de ganancia, stop móvil, salida por tiempo, salida opcional por señal contraria **punto de equilibrio** (desde el 19/11/2026: al ir ganando 0,5–2 veces lo arriesgado, el stop pasa a la entrada más comisiones) y **salida parcial** (19/11/2026: al tocar 1–2 veces lo arriesgado se cierra la mitad y el resto sigue con el stop en la entrada; en Binance es una orden a mercado de media posición y se rehacen stop y toma de ganancia; si la mitad no llega al mínimo de Binance, sigue entera). Igual en pruebas y en vivo.
  - Filtros: tendencia, RSI, ADX, volumen, +DI/-DI, funding, tendencia de BTC, miedo/codicia, horario (Asia/Europa/América) y volatilidad (ATR relativo).
- **Estrategias famosas como semillas** (`fabrica/famosas.py`): Tortugas 20 y 55, cruce dorado 50/200, RSI-2 de Connors, MACD + EMA200, Bollinger Squeeze, rebote Bollinger con ADX bajo (estilo Freqtrade), Supertrend 10/3, nube de Ichimoku, EMA 8/21 + RSI, Turtle Soup, Double 7s, Keltner, estocástico con tendencia, vela interior, VWAP, RSI 30/70 con tendencia y 4 variantes de "ruptura de consolidación" (sin filtro, con tendencia, con expansión de ATR, con BTC), con parámetros fijados antes de probar. Entran en cada ciclo y tienen que pasar los mismos exámenes. Además, en cada ciclo entran como semillas las estrategias de la liga que **van ganando en vivo** (5+ operaciones con promedio positivo): la fábrica busca variantes parecidas a lo que funciona hoy.
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
- **Clima del mercado (desde el 19/11/2026):** con las velas de 4 h de Bitcoin se clasifica el mercado en alcista / bajista / lateral (ADX ≥ 20 + precio contra la EMA 200). Cada estrategia guarda cómo le fue en cada clima en sus pruebas (`por_clima`), y cada operación en vivo anota el clima al entrar. Un **titular no entra** en un clima en el que no gana: con 5+ operaciones en vivo en ese clima manda lo vivido; si no, sus pruebas (20+ operaciones con R promedio ≤ 0). Los suplentes no se frenan (siguen juntando datos). Aviso 🧭 cuando cambia el clima; comando `/clima`.
- **Registro de noticias (desde el 18/11/2026):** el radar anota cada noticia importante o grave y cada dato económico de EE.UU. con el precio de Bitcoin, y después cuánto se movió a 1, 4 y 24 horas (`/data/vivo/noticias.json`, máximo ~1 MB). Solo anota, no cambia cómo se opera. `/noticias` muestra el resumen. Revisar en 1–2 meses: si un tipo de noticia mueve el precio siempre para el mismo lado, convertirlo en pieza de la fábrica y examinarlo.
- **Radar:** calendario económico, volatilidad de BTC, noticias (Cointelegraph, CoinDesk) y Miedo y Codicia. Pausa las entradas si hay peligro y avisa por Telegram.

## Plata real: "real parcial" (ACTIVA desde el 3/11/2026)

Solo los bots de `real_parcial.bots` (config.yaml) operan con plata real en la cuenta REAL de Binance; el resto sigue en la demo. Necesita: claves reales `BINANCE_REAL_API_KEY`/`BINANCE_REAL_API_SECRET` (solo futuros, sin retiros, IP 187.77.33.76), `LIVE_TRADING=true`, USDT en la billetera de Futuros real y `/confirmar_real`. Capital propio (`real_parcial.capital`, 50 USDT por defecto → 1% = 0,50 por operación) y frenos propios (diario y total). El bot elegido igual tiene que venir ganando en vivo; si no, sigue en práctica. Activado el 3/11 con XRP 1h (943f10ba0e); primera operación real: +0,94 USDT. Desde el 10/11, pase automático (`real_parcial.auto`): un titular con 10+ operaciones en vivo y promedio ≥ +0,2R pasa solo a plata real, y vuelve a la demo si deja de cumplirlo; todos comparten el capital y los frenos de la cuenta real.

## Pendientes que decide John

- **Riesgo por bot** (programado el 19/11/2026, APAGADO en `config.yaml` → `riesgo_por_bot.activo`): un bot con 20+ operaciones en vivo y ganancia comprobada (t ≥ 2) arriesgaría 1,5%; uno que pierde en promedio, 0,5%. El tope de 3% abierto y los frenos no cambian. Activarlo solo si John lo decide.
- **Cobrar el funding** (comprar en Spot + vender en corto en Futuros la misma cantidad): usaría los USDT de Spot; no está programado.

## Reglas de riesgo (no se tocan)

- 1% de riesgo por operación, máximo 3% en total abierto, apalancamiento máximo 3x.
- Freno diario: −3% en el día, o 2 pérdidas seguidas.
- Freno total: −15% desde el máximo.
- Capital inicial: 100 USD. **Nunca aumentar el capital automáticamente.**
- Plata real **solo** con `MODO=real` + `LIVE_TRADING=true` + confirmación por Telegram (`/confirmar_real`).

## Telegram

- Bot: "Sistema de ganancias".
- Comandos: /estado /hoy /bots /fabrica /noticias (registro de noticias) /clima (clima del mercado) /ciclo (correr la fábrica ahora) /salud (chequeo automático: datos, ciclos, disco, bots) /diagnostico (¿hubo señales sin operar?) /graduacion (¿cuánto falta para plata real?) /pausar /reanudar /cerrar_todo /informe /radar /ayuda.
- Resumen nocturno a las 22 h (hora de Montevideo). Ciclo semanal de la fábrica: domingo 3:00 UTC.

## Dónde corre

- Servidor VPS de Hostinger KVM 2 (2 núcleos, 8 GB, IP 187.77.33.76), con **Easypanel** (entrar desde hPanel → VPS → "Gestionar panel"): proyecto `orangutanjh`, servicio `fabrica`. n8n está apagado (no se usa).
- Fuente en Easypanel: GitHub `johnsosa627-lang/Nexaris`, rama `main`, ruta `/fabrica`, Dockerfile.
- Variables de entorno (Easypanel → fabrica → Entorno), 7 líneas: `TELEGRAM_TOKEN`, `BINANCE_API_KEY` y `BINANCE_API_SECRET` (cuenta DEMO), `MODO=testnet`, `BINANCE_REAL_API_KEY` y `BINANCE_REAL_API_SECRET` (cuenta REAL: solo futuros, sin retiros, IP restringida), `LIVE_TRADING=true`. Los valores NUNCA se escriben en el repositorio ni en el chat.
- Almacenamiento (montaje de volumen): `fabrica-datos` → `/data` (datos, banco de estrategias, estado de la liga y operaciones; sobrevive a las actualizaciones).
- **Para actualizar a la última versión** (Easypanel no vuelve a armar la imagen), en la Consola web de Hostinger (hPanel → VPS → Consola web):

  ```
  curl -fsSL https://raw.githubusercontent.com/johnsosa627-lang/Nexaris/main/fabrica/actualizar.sh | bash
  ```

  Trabaja solo en segundo plano y avisa por Telegram si salió bien (✅) o mal (❌). No pegarlo mientras corre un ciclo de la fábrica (si pasa, el ciclo se retoma solo).
- Diagnóstico desde la Consola web: `docker logs --tail 30 $(docker ps -q -f name=orangutanjh_fabrica) 2>&1` y `docker service ps orangutanjh_fabrica`.
- Consejos: no usar el traductor de Chrome en Easypanel (rompe la página). En Easypanel los nombres van en minúsculas.

## Estado al 22/11/2026 (decisión de fondeo + modo examen listo)

- **Decisión de John (22/11):** entrar a una cuenta de fondeo de verdad después de la revisión del domingo próximo, aunque sea poco tiempo. John asume el riesgo ("si va mal es mi riesgo"). Renovó Hostinger por el mes. Rol de la IA: que si lo hacemos, sea lo más inteligente posible (ensayo en demo de Bybit antes de pagar, empezar por el examen más chico ~$89).
- **Bybit probado hoy (22/11):** John creó cuenta Bybit + demo + claves de API (solo operar, sin retiros, sin IP, validez 3 meses). Se corrió `fabrica/probar_bybit.py` en el servidor: conectó a la demo (saldo 50.000 USDT de mentira) y la prueba `--orden XRP` abrió, puso stop y cerró → "el ejecutor de Bybit funciona". (Las claves demo se vieron en fotos; conviene recrearlas antes del examen real.)
- **Modo examen listo (apagado):** config `fondeo.activo:false`. Trae: comando `/examen` (cuánto falta para la meta y margen hasta los límites), y ahora el **freno del examen** — con el modo prendido, la cuenta principal frena al `margen_freno` (80%) del límite del examen (ej. total 6% → frena a 4.8%), para no reventarlo. Con el modo apagado NO cambia nada. 186 tests pasan.
- **Plan de la semana:** lun-sáb los bots juntan operaciones; la IA deja listo el modo examen con las reglas de HyroTrader. Domingo: revisar `/racha` y `/informe`; si viene bien, arrancar el ensayo en Bybit demo (EXCHANGE=bybit + fondeo.activo:true). Cuando el ensayo aguante las reglas → pagar el examen real.
- Pendiente menor: pulir `probar_bybit` para que no muestre el aviso de "trades >2 años" (usa fecha 0 en la prueba; inofensivo).

## Estado al 20/11/2026 (adelantamos la decisión del domingo)

- **"Lo del domingo" se hizo el 20/11** (jueves), todo 🟢: revisado /estado, /bots, /informe, /graduacion.
- **Cuenta REAL subida a 80 USDT:** `real_parcial.capital` 50 → 80. John pasó 38 USDT de Spot a Futuros real (quedó ~90,93 en la billetera; el sistema arriesga sobre 80, el resto es colchón). El riesgo sigue 1% por operación; los frenos no cambian.
- **Dos bots operan con plata real:** `943f10ba0e` (XRP 1h, elegido a mano) y `6cee94d171` (XRP 1h), que pasó solo por el pase automático (10 ops, +1.06R). Comparten los mismos 80 USDT y el tope de 3% abierto: más bots = más operaciones, no más riesgo. John eligió dejar los dos (20/11).
- **Cuenta demo:** 103,60 USDT (máximo 103,60). 7 titulares, 28 suplentes. Clima: bajista.
- **Aplicado el 20/11 (PR #79 + #80):** temporalidad 30m (más señales, misma exigencia; baja la historia sola), ejecutor de Bybit listo pero APAGADO (`EXCHANGE=bybit`, para fondeo), variedad del banco, y el comando **/racha** (ganadas/perdidas por titular y cuánto falta para 20 ops). Tests: 175 pasan.
- **Bug que ya se arregló (20/11):** al cambiar a Bybit saqué `EjecutorBinance` de un import y el contenedor se cerraba al arrancar con claves reales (la versión vieja siguió andando, no se cortó el trading). Arreglado y con un test estático (pyflakes) que frena cualquier nombre sin definir.
- **Pendiente:** reiniciar el servidor ("System restart required"); se dejó para otro día porque estaba bajando la historia de 30m. No corre `actualizar.sh` con un ciclo en marcha (el ciclo es los domingos 3:00 UTC).
- **Rotar** el token de Telegram y la contraseña de Easypanel (quedaron a la vista en fotos).

## Estado al 15/11/2026

- **Cuenta de práctica (demo de Binance):** 102,74 USDT (arrancó en 100; mínimo ~91,9 el 5/11). Semana del 8 al 15/11: titulares +12,22 USDT. 7 titulares y ~29 suplentes. Banco: 276 estrategias. Examen de graduación: 4 de 5 ✅ (falta un bot con 30+ operaciones ganando; el que más tiene lleva 10).
- **Cuenta REAL:** 52,47 USDT (arrancó en 50,00 el 3/11). Bot con plata real: XRP 1h `943f10ba0e`. 4 operaciones reales, las 4 ganadas (todas ventas en corto de XRP en un mercado bajista: falta ver cómo le va cuando el mercado cambie).
- Mercado: miedo extremo (10/100) a mediados de noviembre, Bitcoin ~76.000, secuelas del hackeo de Binance.
- Idea de John para el 22/11 si sigue 🟢: subir la plata real a 80 USDT (él pasa 30 USDT más a Futuros; se cambia `real_parcial.capital` a 80).
- Plata de John en Binance (real): ~50 USDT en Futuros (los usa el sistema), ~50 USDT en Spot y ~35 TRX (no los toca el sistema).
- Tests: 170 pasan (`cd fabrica && python -m pytest -q`).
- Problemas ya resueltos que pueden volver: Telegram cortando las esperas largas (ahora pasa solo a conexiones cortas); ciclo cortado por una actualización (se retoma solo); caída del servidor por memoria (n8n apagado; el ciclo usa un proceso nuevo por moneda).

## Próximos pasos

1. ✅ Demo de Binance (octubre) y ✅ plata real chica con 50 USDT (desde el 3/11).
2. **Domingo 22/11:** decisión con las reglas de abajo (y renovar Hostinger antes de que venza).
3. Con bots de 20–30 operaciones en vivo: comparar real contra práctica (precios, comisiones), y recién ahí subir la plata de a poco (50 → 100 → 200) y considerar riesgo por bot e interés compuesto.
4. Opcional, por seguridad: cambiar el token del bot en BotFather y la contraseña de Easypanel (estuvieron visibles en fotos).

## Plan acordado (31/10/2026): de la demo a la cuenta de fondeo

1. **Ahora (2–4 semanas):** que la liga encuentre 2–3 bots graduados (30+ operaciones en vivo ganando, prueba t ≥ 2) en la demo de Binance.
2. **Plata real chica (1–2 meses):** 50–100 USD con los mismos frenos, para confirmar que con plata real gana igual que en la demo.
3. **Cuenta de fondeo (FTMO u otra que permita bots y cripto):** adaptar frenos a sus reglas (−5% diario, −10% total) y conectar a su plataforma.
4. **Crecer:** más cuentas de fondeo y quizás el servicio de "probador de estrategias".
No saltear etapas. Si los datos dicen que no gana, decirlo claro y buscar otro camino.

## Decisión del domingo 22/11/2026 (acordada el 11/11, antes de renovar Hostinger)

Mirar tres números: (1) cuenta de práctica desde el 30/10 (ese día ~94,7; el 11/11 iba 96,5); (2) cuenta REAL (empezó en 50,00; el 11/11 iba 50,94); (3) cuántos bots tienen 5+ operaciones en vivo ganando.
- 🟢 Práctica y real arriba: seguir y renovar Hostinger por más meses (más barato); con bots de 20–30 operaciones, subir la plata de a poco y considerar riesgo por bot (0,5–1,5%) e interés compuesto (decisión de John).
- 🟡 Parejas: renovar 1 mes más; faltan datos.
- 🔴 Las dos claramente abajo: frenar la plata real (/pausar), sacar los USDT y pensar otro camino (otras estrategias o cuenta de fondeo).
Ojo: en 3 semanas hay pocas operaciones; se decide con señales, no con certezas.
✅ Adelantado al 18/11 (pedido de John): se sumaron 5 monedas grandes con historia desde 2021 (TRX, DOT, NEAR, ATOM, BCH; SUI y TON se descartaron por tener poca historia) → de 10 a 15 monedas, y hasta 45 suplentes. No "todas las monedas" (las chicas se manipulan y no tienen historia) ni operaciones para ganar centavos (las comisiones se las comen). Vigilar memoria del servidor en el primer ciclo con 15.

## Meta: ganar 3.000 USD por mes con cuentas de fondeo (acordada el 18/11/2026)

Cuentas: con un mes bueno (+5%) hace falta operar ~60.000–75.000 USD; la empresa de fondeo se queda con 10–20% de la ganancia. No es para este mes: es un plan de varios meses y depende de que el sistema siga ganando.

1. **Ahora → fin de noviembre:** el bot real (XRP 1h) y los que pasen solos junten operaciones reales; el 22/11 decidir 🟢/🟡/🔴 y, si 🟢, subir la plata real a 80 USD.
2. **Diciembre — elegir la empresa:** una que permita bots por API en cripto. Candidata: **HyroTrader** (bots propios por API en una cuenta demo de **Bybit**; prohíbe alta frecuencia y sistemas comprados). Otras a revisar: Crypto Fund Trader, BrightFunded, Velotrade (API en cuentas fondeadas). Leer el reglamento vigente antes de pagar (cambian seguido; no hay ninguna confirmada con Binance).
3. **Adaptar el sistema:** conectar Bybit (ccxt ya lo soporta), frenos con los límites exactos de la empresa (nuestro −3% diario ya es más estricto que su −5%; el freno total pasa de −15% a su límite, p. ej. −10%), y un modo "examen" que avise cuánto falta para la meta del examen.
   - **Hecho (19/11/2026, apagado):** el ejecutor ya está listo para Bybit. En `ejecutor.py` está `EjecutorBybit` (hereda de `EjecutorBinance`; solo cambian el saldo unificado y que la ganancia realizada viene en `info.execPnl`) y `crear_cliente_bybit`. Se prende con la variable `EXCHANGE=bybit` (por defecto `binance`, o sea no cambia nada hoy). Las claves de Bybit van en `BINANCE_API_KEY`/`BINANCE_API_SECRET`. Falta todavía: probar en demo de Bybit con las reglas puestas, el modo "examen" y los frenos exactos de HyroTrader (1 paso: meta 10%, −4% diario, −6% total trailing; 2 pasos: 10%+5%, −5% diario, −10% total). Reglamento/precios HyroTrader a confirmar en su web (≈USD 89 la cuenta chica).
4. **Primer examen: cuenta de 10.000 USD** (costo bajo). Si aprueba: ~+400 USD/mes en un mes bueno.
5. **Escalar:** cuentas de 50.000–100.000 USD (varias empresas suben el tamaño si se gana parejo) → ~2.000–4.500 USD/mes en un mes bueno.
Riesgo: lo máximo que se pierde en cada intento es lo que cuesta el examen.

## Ideas guardadas para más adelante (no ahora)

- **FTMO / MetaTrader** (alternativa a las empresas de fondeo cripto con API; ver la meta de 3.000 USD/mes): examen pago, reglas de −5% diario y −10% total (parecidas a nuestros frenos; habría que poner el freno total en −10%), bots en MetaTrader 5 (su conexión con Python necesita Windows) y la fábrica aprendiendo con datos de forex/oro.
- **Piezas nuevas para la fábrica:** interés abierto y liquidaciones de Binance.
- **Salidas parciales:** cerrar la mitad en ganancia y dejar correr el resto.
- **"Te pruebo tu estrategia":** vender por Telegram informes del probador anti-suerte para la estrategia que pida el cliente (sin manejar plata ni claves de nadie; consultar con un contador antes de cobrar).
- **Oro, Nasdaq y acciones:** necesitan años de historia y otro bróker para acciones.

## Cómo trabajamos (para la IA que me ayude)

- Yo (John) mando fotos de Telegram (/estado, /bots, /informe, /fabrica, /salud, /diagnostico y el resumen de las 22 h). La IA las lee, explica en simple, **detecta cualquier cosa rara** y, si es un error del sistema, lo arregla en el código, corre los tests, sube el cambio (rama de trabajo → pull request → merge a `main`) y me da el comando de actualización.
- La IA no ve el servidor ni Telegram directamente: solo lo que le mando. Para diagnosticar me pide comandos para la Consola web.
- Ser proactiva: proponer mejoras basadas en los datos, pero de a una y midiendo antes de cambiar más.
- Cuidado con estafas: trading de redes sociales, opciones binarias (IQ Option, Pocket Option), "señales" y "IA que gana sola". Avisarme.

## Reglas para la IA que me ayude

- Nunca publicar tokens, claves ni contraseñas en el código ni en GitHub (el repositorio es público).
- No sacar las protecciones ni bajar la exigencia de los exámenes para que opere más.
- No operar ni mover plata por mí.
- Probar todo con los tests antes de subir cambios.
- Nunca subir la plata real ni el riesgo sin que yo lo decida; nunca habilitar retiros en las claves.
