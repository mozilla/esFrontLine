FROM nginx:alpine

EXPOSE 80

RUN rm /etc/nginx/conf.d/default.conf
COPY proxy.conf /etc/nginx/conf.d/proxy.conf

CMD nginx -g 'daemon off;'
