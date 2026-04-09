# Portal gateway. Serves the static landing page and reverse-proxies
# each module by path prefix. No build step, just static HTML + nginx.

FROM nginx:1.27-alpine

COPY index.html /usr/share/nginx/html/index.html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
