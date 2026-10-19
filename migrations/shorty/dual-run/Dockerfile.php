# Dual-run PHP side — runs unmodified mikecao/shorty against MySQL 8.
# Used by docker-compose.yml in this directory.
#
# Build context is `..` (the migration root) so we can COPY both
# `source/` and `dual-run/php-overlay/` into the image. Baking the source
# into the image (rather than bind-mounting from a read-only host dir)
# sidesteps Docker's "can't create mountpoint inside a RO bind" failure.
#
# This container is bound to 127.0.0.1 only by docker-compose.

FROM php:8.2-apache

# Enable mod_rewrite (required by shorty's pretty-URL routing).
RUN a2enmod rewrite

# Install PDO MySQL driver.
RUN docker-php-ext-install pdo pdo_mysql

# Allow .htaccess overrides on /var/www/html.
RUN printf '<Directory /var/www/html>\n  AllowOverride All\n  Require all granted\n</Directory>\n' \
    > /etc/apache2/conf-enabled/shorty.conf

WORKDIR /var/www/html

# Bake the unmodified legacy source + overlay into the image. The source
# directory is chmod a-w on the host (engagement lock); copying it in
# means the container has a writable copy at runtime which Apache needs
# (e.g. for log files), while the original on host remains untouched.
COPY source/ /var/www/html/
COPY dual-run/php-overlay/.htaccess /var/www/html/.htaccess
COPY dual-run/php-overlay/config.php /var/www/html/config.php

# Default Apache port (mapped to 127.0.0.1 by compose only).
EXPOSE 80
