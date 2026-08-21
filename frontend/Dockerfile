# syntax=docker/dockerfile:1
# ==============================================================================
# CodeMorph AI Frontend Dockerfile
# Multi-stage build for React 19 + Vite + Nginx - BuildKit Optimized
# ==============================================================================

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package management files
COPY package.json package-lock.json ./

# Install dependencies with npm cache mount
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Copy application source (excluding node_modules via .dockerignore)
COPY . .

# Build the Vite application
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine

# Create a non-root user for Nginx
RUN adduser -D -H -u 1001 -s /sbin/nologin appuser && \
    chown -R appuser:appuser /usr/share/nginx/html && \
    chown -R appuser:appuser /var/cache/nginx && \
    chown -R appuser:appuser /var/log/nginx && \
    chown -R appuser:appuser /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R appuser:appuser /var/run/nginx.pid

# Overwrite default nginx config to run on port 3000, handle client-side routing, and proxy API requests
RUN echo 'server { \
    listen 3000; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /api/v1/ws/ { \
        proxy_pass http://codemigration-backend-api:8000; \
        proxy_http_version 1.1; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "Upgrade"; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
    } \
    location /api/ { \
        proxy_pass http://codemigration-backend-api:8000; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
    } \
}' > /etc/nginx/conf.d/default.conf

# Copy the built assets from the builder stage
COPY --from=builder --chown=appuser:appuser /app/dist /usr/share/nginx/html

# Switch to non-root user
USER appuser

# Expose port (must be >1024 for non-root)
EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
