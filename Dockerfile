FROM python:3.12-slim-bookworm
LABEL maintainer="Luis Perez <luis.perez.live@gmail.com>"

WORKDIR /app

# Copy our local files over to /app so we can update the local installation.
COPY . /app

RUN pip3 install pipenv

RUN chmod a+x /app/serve.sh


