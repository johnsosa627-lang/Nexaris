# Bot de futuros Binance USDT-M (manejado por Telegram)

Bot en Python que opera futuros perpetuos USDT-M de Binance (por defecto **XRP/USDT:USDT en 15m**),
con filtro de IA vía OpenRouter, protecciones obligatorias y control total desde el teléfono por Telegram.
Pensado para desplegarse en **Easypanel** (Docker) con un capital inicial de **15 USDT**.

> ⚠️ **Aviso de riesgo:** operar futuros con apalancamiento puede hacerte perder todo el capital.
> Este bot no garantiza ganancias. Empezá **siempre** en `MODO=papel`, después `testnet`, y recién
> al final `real` con plata que puedas perder.

---

## 1. Qué hace

**Estrategia (solo sobre velas cerradas)**

| | LONG | SHORT |
|---|---|---|
| Cruce EMA | EMA 9 cruza **arriba** de EMA 21 | EMA 9 cruza **abajo** de EMA 21 |
| RSI (14) | entre 50 y 70 | entre 30 y 50 |
| Histograma MACD (12,26,9) | > 0 | < 0 |
| Bollinger (20, 2) | cierre **debajo** de la banda superior | cierre **arriba** de la banda inferior |
| Volumen | mayor a su media de 20 velas | mayor a su media de 20 velas |

**Filtro IA:** si hay señal técnica, se mandan las últimas 20 velas con indicadores a OpenRouter
(`nex-agi/nex-n2.5-pro:free`, respaldo `nex-agi/nex-n2.5-mini`). La IA devuelve
`{"score": 0-100, "motivo": "..."}`. Solo entra si `score >= 60`. Si la IA falla o se agota el
presupuesto diario/semanal de llamadas, **no opera**. Cada intento HTTP cuenta como una llamada.

**Protecciones (sin martingala):**

- Margen **aislado**, apalancamiento máximo **3x** (tope en el código aunque la variable diga más).
- Usa el **90 % del saldo** como margen por operación (15 USDT → ~40,5 USDT de nocional).
- **Stop-loss 3 %** y **take-profit 6 %** (de movimiento del precio) colocados en el exchange como
  órdenes `reduceOnly`, y además **vigilados por software cada 30 s** por si la orden falla.
  Con 3x, un SL de 3 % equivale a perder ~9 % del margen.
- **Una sola posición** a la vez y **máximo 5 operaciones por día**.
- **Corte diario**: si pierde 20 % en el día (UTC), no opera hasta el día siguiente.
- **Apagado automático** si el saldo baja de 10 USDT (avisa por Telegram). Queda apagado aunque se
  reinicie el contenedor; si cargás saldo, usá `/reactivar`.
- Antes de cada orden verifica **cantidad mínima y nocional mínimo** del par; si no alcanza, avisa y no opera.
- **Al reiniciar** lee la posición abierta del exchange: si existe la adopta (y repone SL/TP), nunca duplica.
- Los comandos de Telegram enviados mientras el bot estaba apagado se descartan (para que un `/cerrar` viejo no se ejecute de sorpresa).

**Modos (`MODO`)**

- `papel`: precios reales de Binance, operaciones simuladas con saldo virtual de 15 USDT y comisión 0,05 % por lado.
- `testnet`: cuenta **Demo Trading** de Binance Futures (reemplazó al viejo testnet).
- `real`: plata real. **Solo funciona si `CONFIRMAR_REAL=SI`**; si no, el bot queda apagado y avisa.

Cada modo guarda su propio estado (`estado_papel.json`, `estado_testnet.json`, `estado_real.json`).

---

## 2. Comandos de Telegram

Solo responde a tu `TELEGRAM_CHAT_ID`; cualquier otro chat es ignorado.

| Comando | Qué hace |
|---|---|
| `/estado` | Modo, saldo, posición abierta (con flotante), resultado del día y total, uso de IA |
| `/pausar` | No abre nuevas operaciones (la posición abierta sigue vigilada) |
| `/reanudar` | Vuelve a operar |
| `/cerrar` | Cierra la posición abierta a mercado |
| `/operaciones` | Últimas 10 operaciones con resultado |
| `/reactivar` | Reactiva el bot tras un apagado por saldo (solo si el saldo ≥ mínimo) |
| `/ayuda` | Lista de comandos |

Avisos automáticos: inicio, apertura, cierre, señales descartadas (IA, mínimos), errores, corte de seguridad y apagado.

---

## 3. Paso a paso desde el celular

### 3.1 Crear el bot de Telegram (BotFather)

1. En Telegram buscá **@BotFather** (tilde azul) y tocá **Iniciar**.
2. Mandá `/newbot`, elegí un nombre (ej. `Mi Bot Futuros`) y un usuario que termine en `bot`
   (ej. `mi_futuros_bot`).
3. BotFather te responde con un **token** tipo `123456789:AAH...`. Ese es tu `TELEGRAM_TOKEN`.
   No lo compartas.

### 3.2 Obtener tu chat ID

1. Abrí tu bot nuevo (el link `t.me/mi_futuros_bot`) y mandale cualquier mensaje, por ejemplo `hola`.
2. En el navegador del celular abrí (reemplazando el token):
   `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
3. Buscá `"chat":{"id":123456789,...}`. Ese número es tu `TELEGRAM_CHAT_ID`.
   (Alternativa: hablale a **@userinfobot** y te dice tu ID.)

### 3.3 Crear la API key de Binance (SIN permiso de retiro)

**Para modo real:**

1. App de Binance → **Perfil** (arriba a la izquierda) → **Gestión de API** / **API Management**.
   (Si no aparece en la app, entrá a binance.com desde el navegador del celular en "versión de escritorio".)
2. **Crear API** → tipo **Generada por el sistema** → poné una etiqueta (ej. `bot-futuros`) → verificá con 2FA.
3. Guardá la **API Key** y la **Secret Key** (la secret se muestra una sola vez).
4. Tocá **Editar restricciones**:
   - ✅ **Habilitar lectura** (Enable Reading)
   - ✅ **Habilitar futuros** (Enable Futures)
   - ❌ **NO habilites retiros** (Enable Withdrawals) — el bot nunca los necesita.
   - ❌ No hace falta Spot/Margin ni transferencias.
   - 🔒 **Restringir acceso a IP de confianza**: poné la IP pública de tu servidor de Easypanel
     (muy recomendado; además Binance puede limitar claves sin restricción de IP).
5. Tenés que tener la cuenta de **Futuros USDⓈ-M activada** y transferir los USDT de Spot a Futuros
   (Billetera → Transferir → de Spot a USDⓈ-M Futuros).

**Para modo testnet (Demo Trading):**

1. Entrá a **demo.binance.com** (o en la app: activar **Demo Trading**) y abrí Futuros USDⓈ-M.
2. En el menú de la cuenta demo andá a **API Management** y creá una clave (sin retiros).
3. Esas claves son las que van en `BINANCE_API_KEY` / `BINANCE_API_SECRET` con `MODO=testnet`.
   Las claves demo **no** sirven en real y viceversa.

> En modo `papel` no hacen falta claves de Binance.

### 3.4 Clave de OpenRouter

1. Entrá a **openrouter.ai**, creá una cuenta y andá a **Keys** → **Create Key**.
2. Copiala como `OPENROUTER_API_KEY`.
3. Los modelos `:free` tienen límites de uso. El modelo de respaldo `nex-agi/nex-n2.5-mini`
   puede no ser gratuito (necesita crédito). Si algún modelo cambia de nombre, cambiá `IA_MODELO` /
   `IA_MODELO_RESPALDO` sin tocar el código.

### 3.5 Desplegar en Easypanel

1. Entrá al panel de Easypanel desde el navegador del celular (`http://IP-DE-TU-SERVIDOR:3000`).
2. **Crear proyecto** (ej. `trading`) → dentro del proyecto **+ Service** → **App**. Nombre: `bot-futuros`.
3. Pestaña **Source** → **GitHub**:
   - Owner: `johnsosa627-lang` · Repository: `Nexaris` · Branch: la rama donde esté el bot
   - **Build Path**: `/bot-futuros`
   - Guardá.
4. Pestaña **Build** → elegí **Dockerfile** (archivo `Dockerfile`). Guardá.
5. Pestaña **Environment** → pegá el contenido de `.env.example` y completá tus claves.
   Arrancá con `MODO=papel`. Guardá.
6. Pestaña **Mounts** → **Add Volume**: nombre `datos`, **Mount Path** `/data`. Guardá.
   Ahí quedan el estado, el CSV de operaciones y el log aunque redeployes.
7. No necesita dominio ni puertos (no expone nada, solo habla hacia afuera).
8. Tocá **Deploy**. En unos segundos te llega por Telegram: `🤖 Bot iniciado`. Probá `/estado`.
9. Logs en vivo: pestaña **Logs** del servicio, o el archivo `/data/eventos.log`.

**Pasar de papel → testnet → real:** cambiá `MODO` (y las claves correspondientes) en
**Environment** y tocá **Deploy** de nuevo. Para real además poné `CONFIRMAR_REAL=SI`.

**Actualizar el código:** hacé push a la rama y tocá **Deploy** (o activá auto-deploy).

---

## 4. Archivos en el volumen `/data`

| Archivo | Contenido |
|---|---|
| `operaciones.csv` | `fecha, fecha_apertura, modo, simbolo, lado, entrada, salida, cantidad, resultado_usdt, motivo_cierre` |
| `eventos.log` | Log de eventos (rotativo, 5 × 2 MB) |
| `estado_<modo>.json` | Estado persistente: pausa, apagado, posición, contadores del día, uso de IA, saldo virtual |

El resultado en USDT es **neto de comisiones**. En testnet/real se toma del exchange (PnL realizado
menos comisiones); si no se puede leer, se calcula con 0,05 % por lado.

---

## 5. Variables de entorno

Todas están en `.env.example` con sus valores por defecto. Las claves (`BINANCE_API_KEY`,
`BINANCE_API_SECRET`, `OPENROUTER_API_KEY`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`) van solo como
variables de entorno; nunca en el código ni en el repositorio.

---

## 6. Desarrollo y pruebas

```bash
cd bot-futuros
pip install -r requirements-dev.txt
python -m pytest -q
```

Las pruebas usan datos sintéticos (random walks) y un exchange simulado: validan indicadores
(EMA, RSI de Wilder, MACD, Bollinger) contra implementaciones de referencia, cada condición de la
señal, cálculo de cantidad/SL/TP/resultado con comisiones, presupuesto y respaldo de la IA, y el
flujo completo en modo papel (apertura, TP/SL, corte diario, apagado por saldo, máximo diario,
reinicio con posición abierta, comandos de Telegram).

Correr local en modo papel:

```bash
cp .env.example .env   # completá TELEGRAM_* y OPENROUTER_API_KEY
set -a; . ./.env; set +a
DATA_DIR=./data python -m trader.main
```

### Estructura

```
bot-futuros/
├── Dockerfile
├── requirements.txt
├── .env.example
├── trader/
│   ├── main.py          # arranque y bucle cada 30 s
│   ├── bot.py           # lógica: entradas, cierres, protecciones, comandos
│   ├── estrategia.py    # reglas de señal sobre velas cerradas
│   ├── indicadores.py   # EMA, RSI, MACD, Bollinger, media de volumen
│   ├── riesgo.py        # tamaño, SL/TP, resultado, mínimos, corte diario
│   ├── ia.py            # filtro OpenRouter + presupuesto
│   ├── broker.py        # papel / Binance (testnet demo y real) vía ccxt
│   ├── telegram_bot.py  # comandos y avisos
│   ├── estado.py        # estado persistente JSON
│   └── registro.py      # CSV de operaciones y log
└── tests/
```
