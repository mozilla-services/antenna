# This should be kept in sync with the python version used in .devcontainer/Dockerfile and
# docker/Dockerfile
FROM python:3.11.10-slim-bullseye@sha256:d910a25afa706e0b2da4b59990fb59c0495eeab597b5cd777bbdcda8b6530b7e

WORKDIR /app/

RUN groupadd -r kent && useradd --no-log-init -r -g kent kent

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl tini && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install -U 'pip>=20' && \
    pip install --no-cache-dir 'kent==2.0.0'

USER kent

ENTRYPOINT ["tini", "--", "/usr/local/bin/kent-server"]
CMD ["run"]
