# NOTE(smarnach): To upgrade Python to a new minor or major version, see
# https://antenna.readthedocs.io/en/latest/dev.html#upgrading-to-a-new-python-version
FROM --platform=linux/amd64 python:3.11.11-slim-bookworm@sha256:614c8691ab74150465ec9123378cd4dde7a6e57be9e558c3108df40664667a4c

# Set up user and group
ARG groupid=10001
ARG userid=10001

WORKDIR /app/
RUN groupadd --gid $groupid app && \
    useradd -g app --uid $userid --shell /usr/sbin/nologin --create-home app && \
    chown app:app /app/

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        apt-transport-https \
        build-essential \
        git \
        gcc && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY --chown=app:app requirements.txt /app/

RUN pip install -U 'pip>=20' && \
    pip install --no-cache-dir --no-deps --only-binary :all: -r requirements.txt && \
    pip check --disable-pip-version-check

USER app

# Install the app
COPY --chown=app:app . /app/

# Set Python-related environment variables to reduce annoying-ness
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

ENV PORT 8000
EXPOSE $PORT

ENTRYPOINT ["/app/bin/entrypoint.sh"]
