-- Dual-run PostgreSQL seed — mirrors dual-run/seed.sql (MySQL) row-for-row.
--
-- IDs are pinned explicitly so encoded short codes are identical on both
-- sides. Identity column requires OVERRIDING SYSTEM VALUE for explicit IDs.

-- Schema is created by the FastAPI service via Alembic migration on startup.
-- This file is loaded AFTER schema is ready (via the pg-new entrypoint).

-- Wait for the schema to exist (the FastAPI container creates it via Alembic
-- before this seed runs — the docker-compose `depends_on` + healthcheck
-- handles ordering).

INSERT INTO urls (id, url, created, accessed, hits) OVERRIDING SYSTEM VALUE VALUES
    (1,          'https://example.com/alpha',                  '2026-05-14 00:00:00+00', NULL,                       0),
    (42,         'https://example.com/forty-two',              '2026-05-14 00:00:00+00', '2026-05-14 00:30:00+00',  17),
    (999,        'https://example.com/nine-nine-nine',         '2026-05-14 00:00:00+00', NULL,                       0),
    (12345,      'https://example.com/twelve-thousand',        '2026-05-14 00:00:00+00', '2026-05-14 01:00:00+00',   3),
    (2000000000, 'https://example.com/two-billion-ceiling',    '2026-05-14 00:00:00+00', NULL,                       0)
ON CONFLICT (id) DO NOTHING;

-- Advance the identity sequence past the seeded max so future inserts get
-- non-colliding IDs.
SELECT setval(
    pg_get_serial_sequence('urls', 'id'),
    GREATEST((SELECT MAX(id) FROM urls), 1)
);
