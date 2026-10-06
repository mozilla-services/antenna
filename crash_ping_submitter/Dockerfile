# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# NOTE: This image is for local development and CI only. In production the GCP
# Python buildpack builds the function from the source zip, so this Dockerfile
# is not used in that context.
#
# NOTE: This image includes uv. The installed version and the version pinned
# for astral-sh/setup-uv in CI need to match.
FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:python3.11-bookworm-slim@sha256:4f5d923c9dcea037f57bda425dd209f3ec643da2f0b74227f68d09dab0b3bb36

ARG groupid=10001
ARG userid=10001

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    UV_PYTHON_DOWNLOADS=0

EXPOSE $PORT

WORKDIR /app

# Add a non-privileged user for installing and running the application
RUN groupadd --gid $groupid app && \
    useradd -g app --uid $userid --shell /usr/sbin/nologin --create-home app && \
    chown app:app /app/

USER app

# Install Python dependencies
RUN --mount=type=cache,uid=$userid,gid=$groupid,target=/home/app/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=app:app . /app

CMD ["functions-framework", "--target=handle_crash_ping", "--port=8000"]
