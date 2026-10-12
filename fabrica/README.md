# Sistema de Ganancias: fábrica de bots que se mejora sola

> ⚠️ Operar futuros puede hacerte perder plata. Este sistema **no garantiza ganancias**.
> Esta versión opera solo en **modo práctica** (plata de mentira) sobre precios reales de Binance.

## Qué hace, explicado simple

1. **Baja los precios** de Binance Futures (BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK; velas de 15 min, 1 h y 4 h). Son datos públicos y no piden cuenta.
2. **La fábrica inventa miles de estrategias** (recetas de cuándo comprar o vender) y las mejora con un algoritmo genético: las mejores se cruzan y mutan.
3. **Coladores** (cada uno descarta las que fallan):
   - métricas mínimas (200+ operaciones, profit factor > 1,3, ganancia/caída > 3, caída máxima < 20 %, curva pareja, SQN > 2, gana en la mayoría de los años);
   - **datos nuevos**: tiene que ganar en una parte de los datos que no usó para crearse;
   - **anti-suerte**: se corre la misma fábrica con precios barajados al azar, y la estrategia tiene que superar lo mejor que salga de ahí. También se usa el *Deflated Sharpe*;
   - **Monte Carlo**: 1000 simulaciones mezclando el orden, salteando operaciones y hasta duplicando costos;
   - **sobreajuste**: si al mover un número un 15 % se rompe, se descarta;
   - **retraso**: tiene que aguantar entrar una vela tarde;
   - **otras monedas**: tiene que funcionar también en la mayoría de las otras.
4. **Examen final**: los últimos 6 meses nunca se usan para crear ni filtrar. Las que pasan todo se prueban ahí **una sola vez**.
5. **Liga de bots**: las que aprueban entran como **suplentes** y operan de práctica. Los **titulares** (hasta 3, que no se parezcan entre sí) manejan la cuenta de práctica de 15 USDT.
   - Un suplente sube a titular cuando demuestra en vivo (30+ operaciones) que anda bien.
   - Un bot **se jubila solo** si cae más de lo peor que había previsto el Monte Carlo, o si rinde mucho menos de lo prometido (prueba estadística). Nunca por un par de días malos.
6. **Frenos de la cuenta**: 1 % de riesgo por operación, freno diario (3 % o 2 pérdidas en el día) y freno total (−15 % desde el máximo: se apaga y avisa).
7. **La fábrica trabaja 24/7**: termina una vuelta, descansa 20 minutos y arranca otra (`ciclo_continuo`). Lleva la cuenta de todas las estrategias probadas en la historia y el *Deflated Sharpe* se vuelve más exigente cuantas más se prueban. Corre con prioridad baja para no molestar a n8n.

Nunca usa martingala, nunca duplica después de perder, y toda operación tiene stop-loss.

## Telegram

`/estado` `/hoy` `/bots` `/fabrica` `/pausar` `/reanudar` `/cerrar_todo` `/informe` `/ciclo` `/ayuda`.
Todas las noches a las 22 h (hora de Uruguay) manda un resumen. Solo le hace caso a tu chat.

## Actualizar (en el servidor)

`bash /root/actualizar_ganancias.sh` baja la última versión de GitHub y reinicia el sistema conservando los datos y el Telegram.

## Instalar en Easypanel

1. Servicio **App**, origen **GitHub** → repositorio `Nexaris`, rama `sistema-ganancias`, carpeta (*build path*) `/fabrica`, método **Dockerfile**.
2. **Environment**: `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` (ver `.env.example`).
3. **Mounts**: un volumen en `/data` (ahí se guardan datos, liga y resultados).
4. **Deploy**.

## Cosas importantes

- **Puede pasar que la fábrica no encuentre ninguna estrategia en un ciclo.** Los filtros son muy exigentes a propósito: en las pruebas con precios inventados al azar, aprueba **cero** estrategias, que es lo correcto.
- La plata real (`LIVE_TRADING`) **no está activada en esta versión**. Se agrega en una etapa posterior, solo si lo pedís y después de semanas de práctica.

## Para desarrolladores

```
pip install -r requirements.txt pytest
python -m pytest -q tests
python -m fabrica.main
```
