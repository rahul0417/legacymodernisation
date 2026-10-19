# Dual-run PHP side — runs unmodified chapagain/crud-php-simple against MySQL 8.
# Build context = migration root (../); we COPY both source/ and the overlay.

FROM php:8.2-apache

RUN docker-php-ext-install mysqli
RUN printf '<Directory /var/www/html>\n  AllowOverride All\n  Require all granted\n</Directory>\n' \
    > /etc/apache2/conf-enabled/crud.conf

WORKDIR /var/www/html

# Bake legacy source + container-aware dbConnection.php into the image.
COPY source/ /var/www/html/
COPY dual-run/php-overlay/dbConnection.php /var/www/html/dbConnection.php

EXPOSE 80
