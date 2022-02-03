FROM python:3.10.2-slim@sha256:9c51896b90ca7175dc8aafcf8408207f404f247728228fb857add24bb26a18fa

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

# Install Socorro Python requirements using pip < 22 because pip 22
# doesn't work with pip-tools. (2022-02-01)
# https://github.com/jazzband/pip-tools/issues/1558
RUN pip install -U 'pip<22' && \
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
