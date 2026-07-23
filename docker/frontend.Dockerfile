FROM node:22-slim

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
# openapi-typescript's peer range still lags TypeScript 6.x.
RUN npm install --legacy-peer-deps

COPY frontend/ ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
