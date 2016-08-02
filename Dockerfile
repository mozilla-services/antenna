# Dockerfile for socorro-collector container
FROM centos:centos7

# Set Python-related environment variables to reduce annoying-ness
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

EXPOSE 8000

# Install pip and get pip8
RUN yum -y install epel-release \
    && yum -y update \
    && yum -y group install "Development Tools" \
    && yum -y install python-devel python-pip
COPY bin/pipstrap.py bin/pipstrap.py
RUN ./bin/pipstrap.py

# Install the app
COPY . /app/
WORKDIR /app/

# Install everything--but do it in a way that busts the cache
# if certain files change
ADD requirements.txt /app/requirements.txt
ADD requirements-dev.txt /app/requirements-dev.txt

RUN pip install --require-hashes -r requirements-dev.txt \
    && pip install -e .
