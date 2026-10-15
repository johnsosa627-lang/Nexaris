#!/usr/bin/env bash
# Actualiza la fábrica que corre en Easypanel a la última versión de GitHub, con un comando corto:
#
#   curl -fsSL https://raw.githubusercontent.com/johnsosa627-lang/Nexaris/main/fabrica/actualizar.sh | bash
#
# Trabaja en segundo plano: aunque se corte la conexión, sigue hasta terminar. Lo que hace queda en
# /root/actualizar.log y el resultado llega por Telegram (con el bot y el chat que ya usa la fábrica).
set -uo pipefail
SERVICIO=orangutanjh_fabrica
IMAGEN=easypanel/orangutanjh/fabrica:latest
REPO=https://github.com/johnsosa627-lang/Nexaris/archive/refs/heads/main.tar.gz
LOG=/root/actualizar.log

if [ "${1:-}" != "trabajar" ]; then
  curl -fsSL https://raw.githubusercontent.com/johnsosa627-lang/Nexaris/main/fabrica/actualizar.sh -o /root/actualizar.sh
  nohup bash /root/actualizar.sh trabajar > "$LOG" 2>&1 < /dev/null &
  echo "✅ Actualización en marcha (sigue sola aunque cierres esto)."
  echo "   En unos minutos te llega el resultado por Telegram."
  echo "   Para ver cómo va: tail $LOG"
  exit 0
fi

avisar() {
  local token chat
  token=$(docker service inspect "$SERVICIO" --format '{{range .Spec.TaskTemplate.ContainerSpec.Env}}{{println .}}{{end}}' \
          | sed -n 's/^TELEGRAM_TOKEN=//p' | sed 's/.*=//' | tr -d ' \r')
  chat=$(docker service inspect "$SERVICIO" --format '{{range .Spec.TaskTemplate.ContainerSpec.Env}}{{println .}}{{end}}' \
          | sed -n 's/^TELEGRAM_CHAT_ID=//p' | tr -d ' \r')
  chat=${chat:-5166367735}
  [ -n "$token" ] && curl -s -o /dev/null "https://api.telegram.org/bot${token}/sendMessage" \
    --data-urlencode "chat_id=${chat}" --data-urlencode "text=$1" || true
}

echo "$(date -u) Bajando la última versión..."
rm -rf /root/nx && mkdir -p /root/nx
if ! curl -fsSL "$REPO" | tar -xz -C /root/nx --strip-components=1; then
  avisar "❌ Actualización: no pude bajar el código de GitHub."; exit 1
fi
echo "$(date -u) Armando el programa..."
if ! docker build -t "$IMAGEN" /root/nx/fabrica; then
  avisar "❌ Actualización: falló al armar el programa. Detalle en $LOG"; exit 1
fi
echo "$(date -u) Reemplazando el programa viejo..."
if ! docker service update --force --detach=false --image "$IMAGEN" "$SERVICIO"; then
  avisar "❌ Actualización: no pude reiniciar la fábrica. Detalle en $LOG"; exit 1
fi
echo "$(date -u) Listo."
avisar "✅ Fábrica actualizada a la última versión. En un rato empieza a bajar la historia completa de precios."
