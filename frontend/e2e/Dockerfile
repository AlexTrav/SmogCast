# браузерные тесты сайта: Playwright с Chromium той же версии, что и пакет @playwright/test
FROM mcr.microsoft.com/playwright:v1.49.1-noble
WORKDIR /e2e
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
CMD ["npx", "playwright", "test"]
