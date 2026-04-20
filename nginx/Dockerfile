FROM nginx:1.25-alpine

RUN rm -f /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/nginx.conf
COPY conf.d/aladino.conf /etc/nginx/conf.d/default.conf