<?php
// Suppress PHP 8 warnings from leaking into output (e.g. undefined-key notices
// promoted to warnings in PHP 8). Matches the shorty harness pattern.
error_reporting(0);
ini_set('display_errors', '0');

$databaseHost     = 'mysql-legacy';
$databaseName     = 'test';
$databaseUsername = 'root';
$databasePassword = 'demo_dev_only';

$mysqli = mysqli_connect($databaseHost, $databaseUsername, $databasePassword, $databaseName);
