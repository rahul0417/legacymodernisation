-- Dual-run MySQL seed — mirrors PG seed row-for-row so dual-run rows are identical.
-- utf8mb3 to fit MySQL 8.4's 3072-byte key limit on VARCHAR-keyed indexes.

CREATE DATABASE IF NOT EXISTS test
  CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci;
USE test;

CREATE TABLE IF NOT EXISTS users (
  id    int(11) NOT NULL auto_increment,
  name  varchar(100) NOT NULL,
  age   int(3)  NOT NULL,
  email varchar(100) NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB CHARACTER SET=utf8mb3;

-- 5 deterministic rows for parity testing. IDs pinned so encoded short URLs
-- (if encoding were involved) and row references stay stable.
INSERT INTO users (id, name, age, email) VALUES
  (1, 'Alice Anderson', 34, 'alice@example.com'),
  (2, 'Bob Baker',      28, 'bob@example.com'),
  (3, 'Carol Chen',     45, 'carol@example.com'),
  (4, 'Dan Diaz',       31, 'dan@example.com'),
  (5, 'Eve Eriksson',   22, 'eve@example.com')
ON DUPLICATE KEY UPDATE id = id;

GRANT ALL PRIVILEGES ON test.* TO 'root'@'%';
FLUSH PRIVILEGES;
