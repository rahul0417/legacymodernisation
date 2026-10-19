# Multi-stage build: Node 20 → nginx for the dual-run harness.
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .
RUN npm run build

FROM nginx:1.25-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
  listen 80;
  server_name localhost;

  root /usr/share/nginx/html;
  index index.html;

  # SPA fallback — all client routes resolve to index.html.
  location / {
    try_files $uri $uri/ /index.html;
  }

  # Dual-run harness proxies /api/ to fastapi-new on the private
  # docker network. In Vite dev, the dev-server proxy handles this
  # and this rule is unused.
  location /api/ {
    proxy_pass http://fastapi-new:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
}
EOF

EXPOSE 80
