# This should be kept in sync with the python version used in .devcontainer/Dockerfile and
# docker/Dockerfile
FROM python:3.11.10-slim-bullseye@sha256:08ef1d5c4e0c05244f0971150437c57f6c79863345e549dbaebaf1b61f56bdf5

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
