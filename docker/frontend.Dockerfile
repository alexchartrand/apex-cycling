FROM node:22-slim

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
# openapi-typescript's peer range still lags TypeScript 6.x.
RUN npm install --legacy-peer-deps

COPY frontend/ ./

EXPOSE 5173

# node_modules lives in an anonymous volume (see docker-compose.yml), which
# would otherwise go stale whenever package.json gains a dependency; a
# no-op install on start keeps it in sync and takes seconds when unchanged.
CMD ["sh", "-c", "npm install --legacy-peer-deps --no-audit --no-fund && npm run dev -- --host 0.0.0.0"]
