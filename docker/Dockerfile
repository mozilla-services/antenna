FROM python:3.8.6-slim@sha256:3a751ba465936180c83904df83436e835b9a919a6331062ae764deefbd3f3b47

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

USER app
EXPOSE $PORT

ENTRYPOINT ["/app/docker/entrypoint.sh"]
