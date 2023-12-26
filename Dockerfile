FROM python:3.12-slim-bookworm
LABEL maintainer="Luis Perez <luis.perez.live@gmail.com>"

WORKDIR /app

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Install dependencies using Pipenv
RUN pip install pipenv && pipenv install --system

# Copy remaining application files
COPY . ./

RUN chmod +x /app/serve.sh

# Set the entrypoint to run your script
CMD ["python", "scraper.py --type='all'"]



