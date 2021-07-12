FROM python:3.9.6-slim@sha256:2c018e29a8eada75e855d78641adda978a2c0a035fd928e281e1240144e8a337

# Set up user and group
ARG groupid=10001
ARG userid=10001

WORKDIR /app/
RUN groupadd --gid $groupid app && \
    useradd -g app --uid $userid --shell /usr/sbin/nologin --create-home app && \
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
