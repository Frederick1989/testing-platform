# Demo web application under test — port 8000
FROM node:20-alpine

WORKDIR /srv/webapp

ENV PORT=8000 \
    WEATHER_URL=http://weather:5000

COPY services/demo-webapp/package.json .
COPY services/demo-webapp/package-lock.json* ./
RUN npm install --omit=dev --no-audit --no-fund

COPY services/demo-webapp/server.js .
COPY services/demo-webapp/public ./public

EXPOSE 8000
CMD ["node", "server.js"]
