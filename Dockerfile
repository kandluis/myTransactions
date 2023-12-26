FROM python:3.12-slim-bookworm
LABEL maintainer="Luis Perez <luis.perez.live@gmail.com>"

WORKDIR /app

# Copy our local files over to /app so we can update the local installation.
COPY . /app

# Update the dependencies as specified by new Pipfile.
RUN pip3 install pipenv
RUN pipenv install --system --deploy

RUN chmod a+x /app/serve.sh


