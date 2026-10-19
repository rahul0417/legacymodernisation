#!/bin/sh
# Entrypoint for the fastapi-new service in the dual-run harness.
# 1. Wait for PG.
# 2. Run Alembic upgrade head (creates the urls table).
# 3. Seed deterministic rows from /app/seed-pg.sql so lookup parity has
#    known fixture IDs identical to the MySQL seed.
# 4. Exec uvicorn.
set -eu

echo "[entrypoint] waiting for PostgreSQL at pg-new:5432..."
until python - <<'PY' 2>/dev/null
import asyncio, asyncpg

async def main():
    c = await asyncpg.connect(
        "postgresql://shorty:shorty_dev_only@pg-new:5432/shorty"
    )
    await c.close()

asyncio.run(main())
PY
do
  sleep 1
done
echo "[entrypoint] PG ready."

echo "[entrypoint] running alembic upgrade head..."
alembic upgrade head

echo "[entrypoint] seeding deterministic rows..."
# Use psql via python — keeps the image deps minimal.
python - <<'PY'
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect('postgresql://shorty:shorty_dev_only@pg-new:5432/shorty')
    with open('/app/seed-pg.sql', 'r') as f:
        sql = f.read()
    await conn.execute(sql)
    await conn.close()
asyncio.run(main())
PY
echo "[entrypoint] seed complete."

echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
