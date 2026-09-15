# NanoCoop Teller Web UI Container
FROM nginx:alpine

COPY packages/nanocoop-teller/nginx.conf /etc/nginx/conf.d/default.conf
COPY packages/nanocoop-teller/dist/ /usr/share/nginx/html/

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
