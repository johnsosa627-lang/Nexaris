#!/usr/bin/env bash
# Instala o ACTUALIZA la fábrica de bots en el servidor, con un solo comando:
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/johnsosa627-lang/Nexaris/main/fabrica/instalar.sh)
#
# La primera vez pide el token de Telegram y tu chat ID (quedan guardados en /root/fabrica.env).
# Las siguientes veces solo actualiza a la última versión, sin perder datos ni la liga.
set -euo pipefail

CONFIG=/root/fabrica.env
CARPETA=/root/fabrica-codigo
REPO=https://github.com/johnsosa627-lang/Nexaris/archive/refs/heads/main.tar.gz
NOMBRE=fabrica

echo "=== Fábrica de bots: instalación / actualización ==="

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: este servidor no tiene Docker. (Easypanel lo instala; ¿estás en el servidor correcto?)"
  exit 1
fi

if [ ! -f "$CONFIG" ]; then
  echo
  echo "Primera instalación. Necesito 2 datos de Telegram (se guardan solo en este servidor)."
  read -r -p "Pegá el TOKEN de tu bot (te lo da @BotFather): " TOKEN < /dev/tty
  read -r -p "Pegá tu CHAT ID (te lo da @userinfobot): " CHAT < /dev/tty
  cat > "$CONFIG" <<EOF
MODO=papel
LIVE_TRADING=false
BINANCE_API_KEY=
BINANCE_API_SECRET=
TELEGRAM_TOKEN=$TOKEN
TELEGRAM_CHAT_ID=$CHAT
FABRICA_DATOS=/data/datos
FABRICA_RESULTADOS=/data/resultados
FABRICA_VIVO=/data/vivo
EOF
  chmod 600 "$CONFIG"
  echo "Guardado en $CONFIG"
else
  echo "Uso la configuración guardada en $CONFIG (para cambiarla: nano $CONFIG)"
fi

echo
echo "1/3 Bajando la última versión del código..."
rm -rf "$CARPETA" && mkdir -p "$CARPETA"
curl -fsSL "$REPO" | tar -xz -C "$CARPETA" --strip-components=1
cd "$CARPETA/fabrica"

echo "2/3 Armando el programa (la primera vez tarda unos minutos)..."
docker build -q -t "$NOMBRE" . >/dev/null

echo "3/3 Prendiendo la fábrica..."
docker rm -f "$NOMBRE" >/dev/null 2>&1 || true
docker run -d --name "$NOMBRE" --restart unless-stopped \
  --env-file "$CONFIG" -v fabrica_datos:/data "$NOMBRE" >/dev/null

sleep 5
if [ "$(docker inspect -f '{{.State.Running}}' "$NOMBRE")" = "true" ]; then
  echo
  echo "✅ LISTO: la fábrica está prendida y va a quedar andando 24/7 (se reinicia sola)."
  echo "   En unos segundos te llega por Telegram: '🤖 Fábrica de bots prendida'."
  echo "   Para actualizar en el futuro, pegá el mismo comando de nuevo."
else
  echo "❌ No arrancó. Estos son los últimos mensajes:"
  docker logs --tail 30 "$NOMBRE" || true
  exit 1
fi

echo
echo "Programas corriendo en el servidor (si hay OTRO bot de trading viejo, hay que apagarlo):"
docker ps --format '  {{.Names}}  ->  {{.Image}}'
