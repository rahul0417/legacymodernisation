-- Dual-run seed data — populates both MySQL (legacy) and PostgreSQL (FastAPI) sides with
-- IDENTICAL known rows so the parity-runner can compare lookup behaviour against
-- pre-existing URLs in addition to create-new-URL behaviour.
--
-- The same logical rows must end up in both DBs. The PG version of this is generated
-- separately (different INSERT syntax + DEFAULT now() handling).
--
-- IMPORTANT: id values are explicitly set. They must match across both DBs so the
-- encoded short codes are stable for parity comparison.

-- utf8mb3 (3-byte) so VARCHAR(1000) UNIQUE index fits MySQL 8.4's 3072-byte
-- key limit. Matches legacy shorty's MySQL 5.x default behaviour
-- (latin1/utf8 with no multi-byte expansion of the indexed key length).
CREATE DATABASE IF NOT EXISTS shorty
  CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci;
USE shorty;

CREATE TABLE IF NOT EXISTS urls (
    id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
    url       VARCHAR(1000) NOT NULL,
    created   DATETIME NOT NULL,
    accessed  DATETIME,
    hits      INT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE (url)
) ENGINE=InnoDB CHARACTER SET=utf8mb3;

-- Seed rows for lookup-side parity testing. IDs cover the encoder's interesting branches:
--   id=1            → single base-62 char with seeded prefix
--   id=42           → small multi-char
--   id=999          → 3-digit boundary
--   id=12345        → mid-range
--   id=2000000000   → near INT32 ceiling (~ INT signed limit)
INSERT INTO urls (id, url, created, accessed, hits) VALUES
    (1,          'https://example.com/alpha',                  '2026-05-14 00:00:00', NULL,                  0),
    (42,         'https://example.com/forty-two',              '2026-05-14 00:00:00', '2026-05-14 00:30:00', 17),
    (999,        'https://example.com/nine-nine-nine',         '2026-05-14 00:00:00', NULL,                  0),
    (12345,      'https://example.com/twelve-thousand',        '2026-05-14 00:00:00', '2026-05-14 01:00:00', 3),
    (2000000000, 'https://example.com/two-billion-ceiling',    '2026-05-14 00:00:00', NULL,                  0)
ON DUPLICATE KEY UPDATE id = id;

GRANT ALL PRIVILEGES ON shorty.* TO 'shorty'@'%';
FLUSH PRIVILEGES;
