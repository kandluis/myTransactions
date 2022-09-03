FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.9

RUN yum update -y
RUN yum install -y \
    git \
    google-chrome-stable \
    libxcb \
    unzip \
    wget 
RUN yum -y clean all

# Copy required project files.
COPY *.py .
COPY Pipfile .
COPY Pipfile.lock .
COPY .env .


# Install pipenv so we can do hermetic setup.
RUN pip3.9 install pipenv
RUN pipenv install --system --deploy --ignore-pipfile

# Fetch latest version of Chrome Driver.
RUN wget -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE`/chromedriver_linux64.zip
RUN unzip /tmp/chromedriver.zip chromedriver


CMD ["index.lambda_handler"]