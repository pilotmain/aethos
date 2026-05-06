# Production Next.js front-end for AethOS Cloud (Phase 51).
FROM node:20-bookworm-slim AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Client-side env must exist before `next build` (baked into the bundle).
ARG NEXT_PUBLIC_AETHOS_API_BASE=http://localhost:8000
ARG NEXT_PUBLIC_STRIPE_PRICE_ID_PRO=
ARG NEXT_PUBLIC_STRIPE_PRICE_ID_BUSINESS=
ENV NEXT_PUBLIC_AETHOS_API_BASE=$NEXT_PUBLIC_AETHOS_API_BASE
ENV NEXT_PUBLIC_STRIPE_PRICE_ID_PRO=$NEXT_PUBLIC_STRIPE_PRICE_ID_PRO
ENV NEXT_PUBLIC_STRIPE_PRICE_ID_BUSINESS=$NEXT_PUBLIC_STRIPE_PRICE_ID_BUSINESS

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-bookworm-slim AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/package.json ./
COPY --from=builder /app/package-lock.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000

CMD ["npm", "run", "start"]
