<?php
// Suppress PHP 8 warnings (e.g. "Undefined array key 'q'") from leaking
// into the HTTP response body. Legacy shorty was written for PHP 5/7
// where these were silent E_NOTICE; PHP 8 promoted them to E_WARNING and
// `display_errors=On` (PHP CLI default in this Apache image) prints them.
error_reporting(0);
ini_set('display_errors', '0');

// Dual-run config — overrides source/config.php at container build time.
// Connects to the `mysql-legacy` service inside the docker network.
// Hostname matches what the parity runner will use for short-URL composition.

$hostname = 'http://php-legacy';

$connection = new PDO(
    'mysql:dbname=shorty;host=mysql-legacy;charset=utf8mb4',
    'shorty',
    'shorty_dev_only'
);

// Default chars from upstream shorty/config.php:9 — keep in sync with FastAPI side.
$chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';

// Gate-1 lock: empty salt, padding=3.
$salt = '';
$padding = 3;
?>
