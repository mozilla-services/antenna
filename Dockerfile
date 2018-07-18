FROM python:3.6.2-slim

WORKDIR /app/
RUN groupadd --gid 10001 app && useradd -g app --uid 10001 --shell /usr/sbin/nologin app

RUN apt-get update && \
    apt-get install -y gcc apt-transport-https build-essential graphviz

COPY ./requirements.txt /app/requirements.txt

RUN pip install -U 'pip>=8' && \
    pip install --no-cache-dir -r requirements.txt

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
