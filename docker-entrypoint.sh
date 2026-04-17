#!/bin/bash
set -e

# Load defaults from .env; docker run -e flags take precedence
if [ -f /app/.env ]; then
    while IFS='=' read -r key value; do
        [[ -z "$key" || "$key" == \#* ]] && continue
        if [ -z "${!key+x}" ]; then
            export "$key=$value"
        fi
    done < /app/.env
fi

if [ "$DB_HOST" = "localhost" ] || [ "$DB_HOST" = "127.0.0.1" ]; then
    PG_VERSION=17

    PG_DATA="/var/lib/postgresql/$PG_VERSION/main"

    if [ ! -f "$PG_DATA/PG_VERSION" ]; then
        rm -rf "$PG_DATA" "/var/lib/postgresql/$PG_VERSION" "/etc/postgresql/$PG_VERSION/main"
        pg_createcluster "$PG_VERSION" main
    fi

    chown -R postgres:postgres /var/lib/postgresql
    pg_ctlcluster "$PG_VERSION" main start

    until pg_isready -q; do sleep 0.5; done

    su - postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'\"" \
        | grep -q 1 \
        || su - postgres -c "psql -c \"CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}'\""

    su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'\"" \
        | grep -q 1 \
        || su - postgres -c "createdb -O '${DB_USER}' '${DB_NAME}'"

    su - postgres -c "psql -d '${DB_NAME}' -c 'CREATE EXTENSION IF NOT EXISTS vector'"
    su - postgres -c "psql -d '${DB_NAME}' -c 'GRANT ALL ON SCHEMA public TO ${DB_USER}'"

    echo "Embedded PostgreSQL ${PG_VERSION} ready with pgvector"
fi

exec python -m src.server "$@"
