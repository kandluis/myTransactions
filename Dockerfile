FROM python:3.12.1-slim-bookworm
LABEL maintainer="Luis Perez <luis.perez.live@gmail.com>"

ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Install dependencies using Pipenv
RUN pip install --root-user-action=ignore pipenv && pipenv install --system

# Copy remaining application files
COPY . ./

RUN chmod +x /app/serve.sh

# Set the entrypoint to run your script
CMD ["python", "scraper.py", "--types=all"]
