# ---- 1. deps ----
FROM node:22-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- 2. build ----
FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Baked in at BUILD time: rewrites and NEXT_PUBLIC_* values.
ARG BACKEND_URL=http://backend:8000
ARG NEXT_PUBLIC_USE_MOCK=false
ENV BACKEND_URL=$BACKEND_URL \
    NEXT_PUBLIC_USE_MOCK=$NEXT_PUBLIC_USE_MOCK \
    NEXT_TELEMETRY_DISABLED=1
# public/ is optional; make sure it exists so the COPY below never fails.
RUN mkdir -p public && npm run build

# ---- 3. run ----
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD wget -q --spider http://127.0.0.1:3000/ || exit 1
CMD ["node", "server.js"]