# Multi-stage frontend image. Same pattern as the compliance
# troubleshooter: build the Vite bundle in node, copy static output
# into a stripped nginx image. No node, no npm, no source in the
# runtime image.

# ---- Build stage -----------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json /app/package.json
RUN npm install --no-audit --no-fund

COPY . /app
RUN npm run build

# ---- Runtime stage ---------------------------------------------------------
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
