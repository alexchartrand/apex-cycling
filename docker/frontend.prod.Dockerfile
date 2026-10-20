FROM node:22-slim AS builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
# openapi-typescript's peer range still lags TypeScript 6.x.
RUN npm ci --legacy-peer-deps

COPY frontend/ ./
# physics.test.ts imports the shared test vectors, and `tsc -b` checks tests.
COPY shared/ /shared/

# Same-origin build: Caddy proxies API paths and serves this bundle from one
# origin/port, so the app talks to itself via relative paths (no CORS needed).
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM caddy:2-alpine

COPY docker/Caddyfile /etc/caddy/Caddyfile
COPY --from=builder /app/dist /srv

EXPOSE 80 443
