#!/bin/sh
# Entrypoint for fastapi-new in the crud dual-run harness.
# 1. Wait for PG.
# 2. Run alembic upgrade head.
# 3. Seed 5 deterministic rows.
# 4. Exec uvicorn.
set -eu

echo "[entrypoint] waiting for PostgreSQL at pg-new:5432..."
until python - <<'PY' 2>/dev/null
import asyncio, asyncpg
async def main():
    c = await asyncpg.connect("postgresql://crud:demo_dev_only@pg-new:5432/crud")
    await c.close()
asyncio.run(main())
PY
do
  sleep 1
done
echo "[entrypoint] PG ready."

echo "[entrypoint] alembic upgrade head..."
alembic upgrade head

echo "[entrypoint] seeding 5 deterministic rows..."
python - <<'PY'
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect("postgresql://crud:demo_dev_only@pg-new:5432/crud")
    with open("/app/seed-pg.sql", "r") as f:
        sql = f.read()
    await conn.execute(sql)
    await conn.close()
asyncio.run(main())
PY
echo "[entrypoint] seed complete."

echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
