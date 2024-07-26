FROM alpine:latest AS htpasswd
RUN apk add --update apache2-utils && rm -rf /var/cache/apk/*
RUN mkdir -p /etc/htpasswd && htpasswd -bc /etc/htpasswd/antenna.htpasswd developer password

FROM us-west1-docker.pkg.dev/moz-fx-platform-artifacts/platform-shared-images/nginx-unprivileged:1.22
RUN rm /etc/nginx/conf.d/*
COPY --from=htpasswd /etc/htpasswd/antenna.htpasswd /etc/htpasswd/antenna.htpasswd
COPY nginx.conf /etc/nginx/nginx.conf
COPY *.conf.template /etc/nginx/templates/
# The default command runs /docker-entrypoint.d/20-envsubst-on-templates.sh, which compiles
# /etc/nginx/templates/*.template files with envsubst and writes them to /etc/nginx/conf.d/
ENV UPSTREAM=127.0.0.1:8000
ENV CLIENT_BODY_TIMEOUT=70s
