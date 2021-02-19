FROM python:3.9.2-slim@sha256:c2551d60d07417cdeb78ec9a40793b12cecb80a798dfb5eba0d99f1b422478bc

# Set up user and group
ARG groupid=10001
ARG userid=10001

WORKDIR /app/
RUN groupadd --gid $groupid app && \
    useradd -g app --uid $userid --shell /usr/sbin/nologin app && \
    chown app:app /app/

RUN apt-get update && \
    apt-get install -y gcc apt-transport-https build-essential graphviz

COPY --chown=app:app requirements.txt /app/

RUN pip install -U 'pip>=10' && \
    pip install --no-cache-dir -r requirements.txt && \
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
