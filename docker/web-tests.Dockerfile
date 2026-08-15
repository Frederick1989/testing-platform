# Web test framework (Playwright runner :6000 + report viewer :6001)
FROM mcr.microsoft.com/playwright:v1.44.1-jammy

WORKDIR /srv/web-tests

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    WEBAPP_URL=http://webapp:8000

COPY services/web-test-framework/package.json .
COPY services/web-test-framework/package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY services/web-test-framework/server.js .
COPY services/web-test-framework/playwright.config.js .
COPY services/web-test-framework/tests ./tests

EXPOSE 6000 6001
CMD ["node", "server.js"]
