<?php
// Router for PHP's development server only. Production should use web-server rewrites.
$path = rawurldecode(parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/');
if (!preg_match('#(?:^|/)\.#', $path) && preg_match('#^/assets/(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+$#', $path)) {
    $file = realpath(__DIR__.$path);
    $assets = realpath(__DIR__.'/assets');
    if ($file && $assets && str_starts_with($file, $assets.DIRECTORY_SEPARATOR) && is_file($file)) return false;
}
// Never expose repository files or PHP source through the development server.
if (preg_match('#(?:^|/)\.#', $path) || str_starts_with($path, '/storage/') || $path === '/router.php' || $path === '/README.md') {
    http_response_code(404);
    exit('Not found');
}
$_SERVER['SCRIPT_NAME'] = '/index.php';
require __DIR__.'/index.php';
