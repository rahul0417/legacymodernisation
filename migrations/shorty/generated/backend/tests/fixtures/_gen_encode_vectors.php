<?php
/**
 * _gen_encode_vectors.php
 *
 * TestGen Stage 6 tool — generates encode_vectors.json by running the
 * legacy PHP Shorty::encode against the locked Gate-1 configuration
 * (salt="", padding=3, default chars) and a seed-branch salt ("testsalt").
 *
 * The output JSON is consumed by tests/unit/test_encode.py to assert
 * byte-for-byte parity between the Python target and the PHP reference.
 *
 * Vectors:
 *   Group A — Gate-1 production config (salt="", padding=3)
 *     n in {1, 10, 25, 26, 42, 52, 61, 62, 100, 999, 1000, 12345,
 *           1000000, 100000000, 2000000000, 2147483647}
 *   Group B — seed-branch coverage (salt="testsalt", padding=3)
 *     n in {1, 10, 100, 1000, 10000}
 *
 * Usage:
 *   php tests/fixtures/_gen_encode_vectors.php > tests/fixtures/encode_vectors.json
 */

require_once __DIR__ . '/../../../../source/shorty.php';

$default_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';

function encode_with(string $chars, string $salt, int $padding, int $n): string {
    $s = new Shorty('http://test', null);
    $s->set_chars($chars);
    $s->set_salt($salt);
    $s->set_padding($padding);
    return $s->encode($n);
}

$group_a = [
    ['id' => 'A1',  'n' => 1,           'salt' => '', 'padding' => 3],
    ['id' => 'A2',  'n' => 10,          'salt' => '', 'padding' => 3],
    ['id' => 'A3',  'n' => 25,          'salt' => '', 'padding' => 3],
    ['id' => 'A4',  'n' => 26,          'salt' => '', 'padding' => 3],
    ['id' => 'A5',  'n' => 42,          'salt' => '', 'padding' => 3],
    ['id' => 'A6',  'n' => 52,          'salt' => '', 'padding' => 3],
    ['id' => 'A7',  'n' => 61,          'salt' => '', 'padding' => 3],
    ['id' => 'A8',  'n' => 62,          'salt' => '', 'padding' => 3],
    ['id' => 'A9',  'n' => 100,         'salt' => '', 'padding' => 3],
    ['id' => 'A10', 'n' => 999,         'salt' => '', 'padding' => 3],
    ['id' => 'A11', 'n' => 1000,        'salt' => '', 'padding' => 3],
    ['id' => 'A12', 'n' => 12345,       'salt' => '', 'padding' => 3],
    ['id' => 'A13', 'n' => 1000000,     'salt' => '', 'padding' => 3],
    ['id' => 'A14', 'n' => 100000000,   'salt' => '', 'padding' => 3],
    ['id' => 'A15', 'n' => 2000000000,  'salt' => '', 'padding' => 3],
    ['id' => 'A16', 'n' => 2147483647,  'salt' => '', 'padding' => 3],
];

$group_b = [
    ['id' => 'B1', 'n' => 1,     'salt' => 'testsalt', 'padding' => 3],
    ['id' => 'B2', 'n' => 10,    'salt' => 'testsalt', 'padding' => 3],
    ['id' => 'B3', 'n' => 100,   'salt' => 'testsalt', 'padding' => 3],
    ['id' => 'B4', 'n' => 1000,  'salt' => 'testsalt', 'padding' => 3],
    ['id' => 'B5', 'n' => 10000, 'salt' => 'testsalt', 'padding' => 3],
];

$vectors = [];
foreach (array_merge($group_a, $group_b) as $v) {
    $vectors[] = [
        'id'            => $v['id'],
        'n'             => $v['n'],
        'salt'          => $v['salt'],
        'padding'       => $v['padding'],
        'expected_code' => encode_with($default_chars, $v['salt'], $v['padding'], $v['n']),
    ];
}

$out = [
    'generated_by'  => 'tests/fixtures/_gen_encode_vectors.php',
    'generated_at'  => date(DATE_ATOM),
    'php_version'   => PHP_VERSION,
    'source_legacy' => 'source/shorty.php',
    'config'        => [
        'chars'   => $default_chars,
        'salt'    => '',
        'padding' => 3,
    ],
    'vectors' => $vectors,
];

echo json_encode($out, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";
