-- Dual-run PG seed — same 5 logical rows as seed.sql (MySQL side).
-- Schema created via Alembic by the fastapi-new container's entrypoint.

INSERT INTO users (id, name, age, email) OVERRIDING SYSTEM VALUE VALUES
  (1, 'Alice Anderson', 34, 'alice@example.com'),
  (2, 'Bob Baker',      28, 'bob@example.com'),
  (3, 'Carol Chen',     45, 'carol@example.com'),
  (4, 'Dan Diaz',       31, 'dan@example.com'),
  (5, 'Eve Eriksson',   22, 'eve@example.com')
ON CONFLICT (id) DO NOTHING;

-- Bump the identity sequence past the seeded max.
SELECT setval(
    pg_get_serial_sequence('users', 'id'),
    GREATEST((SELECT MAX(id) FROM users), 1)
);
