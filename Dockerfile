# Build stage
FROM node:20-slim AS builder

WORKDIR /usr/src/app

# Install build deps for native modules (e.g., sqlite3) + curl and unzip
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    python3 \
    make \
    g++ \
    curl \
    unzip \
  && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm ci

COPY . .

# Pre-download SCM data during build (optional but recommended for reliability)
RUN mkdir -p /usr/src/app/data/scm/extracted && \
    (curl -k --max-time 300 -o /tmp/microdados-scm.zip \
      https://app.anm.gov.br/dadosabertos/SCM/microdados/microdados-scm.zip && \
     unzip -q /tmp/microdados-scm.zip -d /usr/src/app/data/scm/extracted && \
     rm /tmp/microdados-scm.zip && \
     echo "SCM data pre-downloaded successfully") || \
    echo "SCM data download skipped (will download at runtime if needed)"

RUN npm run build \
  && npm prune --omit=dev

# Runtime stage
FROM node:20-slim

ENV NODE_ENV=production
WORKDIR /usr/src/app

# Install CA certificates and curl for network debugging
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/src/app/package*.json ./
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY --from=builder /usr/src/app/dist ./dist
COPY --from=builder /usr/src/app/static ./static
COPY --from=builder /usr/src/app/data ./data

EXPOSE 3000
CMD ["node", "dist/main"]
