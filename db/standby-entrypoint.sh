#!/bin/bash
set -e

echo "[standby] waiting for master..."
until pg_isready -h postgres-master -p 5432 -t 2 >/dev/null 2>&1; do
    sleep 2
done

if [ ! -s "/var/lib/postgresql/data/PG_VERSION" ]; then
    echo "[standby] running pg_basebackup..."
    mkdir -p /var/lib/postgresql/data
    chown -R postgres:postgres /var/lib/postgresql/data
    chmod 700 /var/lib/postgresql/data
    su postgres -c "PGPASSWORD=replpass pg_basebackup -h postgres-master -U replicator -D /var/lib/postgresql/data -Fp -Xs -P -R"
fi

chown -R postgres:postgres /var/lib/postgresql/data
exec docker-entrypoint.sh postgres
