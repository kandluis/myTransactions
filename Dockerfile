FROM public.ecr.aws/lambda/python:3.9

RUN yum update -y
RUN yum install -y \
    git \
    unzip \
    wget && \
    yum -y clean all

# Install pipenv and pyenv so we can do the setup.
RUN pip3.9 install pipenv
RUN curl https://pyenv.run | bash

# Construct local environment and move to output.
WORKDIR /tmp/

COPY Pipfile /tmp/Pipfile
COPY Pipfile.lock /tmp/Pipfile.lock

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy --ignore-pipfile


WORKDIR /opt/output/

# Copy output.
RUN cp -r /tmp/.venv /opt/output/.venv
# Remove bin cause we don't use this.
RUN rm -rf /opt/output/bin

# Fetch local chromedriver.
COPY chromedriver /opt/output/chromedriver

# Make local files available.
COPY __init__.py /opt/output/__init__.py
COPY config.py /opt/output/config.py
COPY scraper.py /opt/output/scraper.py

COPY run.sh /opt/output/run.sh
ENTRYPOINT /opt/output/run.sh