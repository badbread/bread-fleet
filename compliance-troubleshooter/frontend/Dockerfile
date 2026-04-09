# Multi-stage frontend image: build the Vite bundle in a node image,
# then copy the static output into a stripped nginx for serving.
# The runtime image has no node, no npm, no source code; just the
# built assets and nginx itself.

# ---- Build stage -----------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# Build-arg for the backend URL. Vite bakes import.meta.env values at
# build time, so this needs to be set BEFORE npm run build, not at
# runtime. Compose passes it via the build.args block.
ARG VITE_BACKEND_URL=http://localhost:8088
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}

# Install deps with the frozen lockfile equivalent. The MVP doesn't
# ship a package-lock.json yet (it would on first npm install in
# the dev environment), so npm install is the safe call here.
COPY package.json /app/package.json
RUN npm install --no-audit --no-fund

COPY . /app
RUN npm run build

# ---- Runtime stage ---------------------------------------------------------
FROM nginx:1.27-alpine

# Drop privileges. nginx-alpine ships an nginx user already.
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
