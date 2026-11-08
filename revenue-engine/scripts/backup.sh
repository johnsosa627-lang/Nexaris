#!/bin/sh
# Copia de seguridad de la base de datos (comprimida), guardando las últimas 14.
# Uso:  DATABASE_URL=... BACKUP_DIR=/backups sh scripts/backup.sh
# Recomendado: correrlo una vez por día y copiar la carpeta a otro lugar (otro servidor o la nube),
# porque una copia que vive en el mismo servidor se pierde si el servidor se pierde.
set -eu
: "${DATABASE_URL:?Falta DATABASE_URL}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP="${KEEP:-14}"
mkdir -p "$BACKUP_DIR"
FILE="$BACKUP_DIR/revenue-engine-$(date -u +%Y%m%d-%H%M%S).sql.gz"
pg_dump --no-owner --no-privileges "$DATABASE_URL" | gzip > "$FILE"
echo "Copia creada: $FILE"
# Deja solo las últimas $KEEP copias
ls -1t "$BACKUP_DIR"/revenue-engine-*.sql.gz | tail -n +"$((KEEP + 1))" | while read -r old; do
  rm -f -- "$old"
done
