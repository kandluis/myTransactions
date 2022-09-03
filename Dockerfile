FROM public.ecr.aws/lambda/python:3.9

RUN yum update -y
RUN yum install -y \
    git \
    google-chrome-stable \
    yum -y clean all

# Install pipenv so we can do hermetic setup.
RUN pip3.9 install pipenv

# Copy required project files.
COPY *.py .
COPY Pipfile .
COPY Pipfile.lock .
COPY chromedriver chromedriver
COPY .env .

# Setup environment.
RUN pipenv install --system --deploy --ignore-pipfile


CMD ["index.lambda_handler"]