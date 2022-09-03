FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.9

RUN yum update -y
RUN yum install -y \
    git \
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

# Fetch the latest Chrome.
RUN wget -O /tmp/chrome.rpm https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
RUN yum -y install /tmp/chrome.rpm



CMD ["index.lambda_handler"]