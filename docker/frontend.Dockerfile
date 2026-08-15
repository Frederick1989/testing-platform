# UAT Dashboard — Vite build served by nginx (port 7001)
FROM node:20-alpine AS build

WORKDIR /srv/ui

COPY frontend/package.json .
COPY frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY frontend/ .
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_API_TOKEN=dev-token
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_API_TOKEN=$VITE_API_TOKEN
RUN npm run build

FROM nginx:1.27-alpine

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /srv/ui/dist /usr/share/nginx/html

EXPOSE 80
