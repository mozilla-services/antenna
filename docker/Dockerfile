FROM python:3.8.5-slim@sha256:a3ddbd9dcadbf9173bf9466c527aef36c01515dad4e3da5147940268232bd420

# Set up user and group
ARG groupid=10001
ARG userid=10001

WORKDIR /app/
RUN groupadd --gid $groupid app && \
    useradd -g app --uid $userid --shell /usr/sbin/nologin app

RUN apt-get update && \
    apt-get install -y gcc apt-transport-https build-essential graphviz

COPY ./requirements /app/requirements

RUN pip install -U 'pip>=10' && \
    pip install --no-cache-dir -r requirements/default.txt -c requirements/constraints.txt && \
    pip check --disable-pip-version-check

# Install the app
COPY . /app/

# Set Python-related environment variables to reduce annoying-ness
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PORT 8000
ENV GUNICORN_WORKERS 1
ENV GUNICORN_WORKER_CONNECTIONS 4
ENV GUNICORN_WORKER_CLASS gevent
ENV GUNICORN_MAX_REQUESTS 0
ENV GUNICORN_MAX_REQUESTS_JITTER 0
ENV CMD_PREFIX ""

USER app
EXPOSE $PORT

CMD $CMD_PREFIX \
    gunicorn \
    --workers=$GUNICORN_WORKERS \
    --worker-connections=$GUNICORN_WORKER_CONNECTIONS \
    --worker-class=$GUNICORN_WORKER_CLASS \
    --max-requests=$GUNICORN_MAX_REQUESTS \
    --max-requests-jitter=$GUNICORN_MAX_REQUESTS_JITTER \
    --config=antenna/gunicornhooks.py \
    --bind 0.0.0.0:$PORT \
    antenna.wsgi:application
