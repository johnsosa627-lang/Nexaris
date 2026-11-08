# Imagen de Revenue Engine AI para Easypanel o cualquier servidor con Docker.

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    # Límite de memoria de Node: protege a los otros servicios del VPS (la fábrica, n8n).
    NODE_OPTIONS=--max-old-space-size=384
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/next.config.ts ./next.config.ts
COPY --from=build /app/drizzle ./drizzle
COPY --from=build /app/scripts ./scripts
USER node
EXPOSE 3000
# Al arrancar: primero pone la base de datos al día, después inicia la aplicación.
CMD ["sh", "-c", "node scripts/migrate.mjs && npx next start -p ${PORT}"]
