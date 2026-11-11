# ScannerRoom API (US-4.1). TypeScript runs directly through Node's native type
# stripping: no build step, the image ships the sources.
FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY src ./src
COPY drizzle ./drizzle
# Maintenance scripts, run with `docker exec scannerroom-api node scripts/<name>.ts`.
COPY scripts ./scripts
USER node
EXPOSE 3002
CMD ["node", "src/index.ts"]
