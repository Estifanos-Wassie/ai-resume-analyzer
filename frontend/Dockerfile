FROM node:24.21.0-bookworm-slim AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install --global npm@11.19.0 --ignore-scripts && npm ci
COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/src ./src
COPY frontend/public ./public
ARG VITE_API_BASE_URL=http://localhost:8080/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:1.30.6-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
