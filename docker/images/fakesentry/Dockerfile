FROM python:3.10.9-slim@sha256:6862d8ed663a47f649ba5aababed01e44741a032e80d5800db619f5113f65434

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
    pip install --no-cache-dir 'kent==1.2.0'

USER kent

ENTRYPOINT ["tini", "--", "/usr/local/bin/kent-server"]
CMD ["run"]
