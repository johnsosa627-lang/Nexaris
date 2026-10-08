#!/usr/bin/env bash
# Prueba la migración y los permisos en un Postgres local (sin Supabase).
# Uso: DB_URL=postgresql://postgres:postgres@localhost:5432/postgres ./scripts/probar-db.sh
set -euo pipefail
cd "$(dirname "$0")/.."
DB_URL="${DB_URL:-postgresql://postgres:postgres@localhost:5432/postgres}"
BASE="avisame_prueba_$$"

psql "$DB_URL" -qc "create database $BASE" >/dev/null
trap 'psql "$DB_URL" -qc "drop database if exists $BASE" >/dev/null' EXIT
URL="${DB_URL%/*}/$BASE"

psql "$URL" -q -v ON_ERROR_STOP=1 -f pruebas/db/supabase_simulado.sql
psql "$URL" -q -v ON_ERROR_STOP=1 -f supabase/migrations/*.sql
echo "✔ Migración aplicada"
psql "$URL" -q -v ON_ERROR_STOP=1 -f pruebas/db/permisos.sql 2>&1 | sed -e 's/^psql:[^ ]* NOTICE:  /  /' -e 's/^NOTICE:  /  /'
