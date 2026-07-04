# =============================================================================
# FRIDAY Desktop — Multi-stage Docker build
# =============================================================================

# ---- Builder Stage ----
FROM node:22-alpine AS builder

WORKDIR /build

# Copy shared types first
COPY packages/ ./packages/
COPY package.json package-lock.json ./

# Install ALL dependencies (including devDependencies for build)
RUN npm ci --ignore-scripts

# Copy app source
COPY apps/desktop/ ./apps/desktop/
COPY apps/desktop/.env.example ./apps/desktop/.env

# Build
RUN npm run build --workspace=desktop

# ---- Runtime Stage (Nginx) ----
FROM nginx:stable-alpine AS runtime

# Copy built assets from builder
COPY --from=builder /build/apps/desktop/dist /usr/share/nginx/html

# Nginx config for SPA routing
RUN rm /etc/nginx/conf.d/default.conf
COPY apps/desktop/nginx.conf /etc/nginx/conf.d/default.conf

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
