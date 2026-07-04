# Build context is frontend/ itself: `docker compose build frontend`
# or manually: `docker build -t meetmind-frontend .` from inside frontend/.
#
# NOTE: `next build` fetches Google Fonts (next/font/google) at build time, so the
# machine running `docker build` needs internet access — same requirement as running
# `npm run build` outside Docker.

FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000
CMD ["npm", "start"]
