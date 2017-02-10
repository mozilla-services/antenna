FROM python:3.5.2-slim

WORKDIR /app/
RUN groupadd --gid 10001 app && useradd -g app --uid 10001 --shell /usr/sbin/nologin app

RUN apt-get update && \
    apt-get install -y gcc apt-transport-https

COPY ./requirements.txt /app/requirements.txt
COPY ./requirements-newrelic.txt /app/requirements-newrelic.txt

RUN pip install -U 'pip>=8' && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-newrelic.txt

# Install the app
COPY . /app/

# Set Python-related environment variables to reduce annoying-ness
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PORT 8000
ENV GUNICORN_WORKERS 1
ENV GUNICORN_WORKER_CONNECTIONS 4
ENV GUNICORN_WORKER_CLASS gevent

USER app
EXPOSE $PORT

CMD gunicorn \
    --workers=$GUNICORN_WORKERS \
    --worker-connections=$GUNICORN_WORKER_CONNECTIONS \
    --worker-class=$GUNICORN_WORKER_CLASS \
    --bind 0.0.0.0:$PORT \
    antenna.wsgi:application
