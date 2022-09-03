FROM public.ecr.aws/lambda/python:3.9

RUN yum update -y
RUN yum install -y \
    git \
    jq \
    libxcb \
    unzip \
    wget 
RUN yum -y clean all

# Install chromium.
WORKDIR /tmp

ADD chromium/build.sh .
ADD chromium/latest.sh .

RUN CHROMIUM_VERSION=$(./latest.sh stable) sh ./build.sh
RUN ln -s /bin/headless-chromium /usr/bin/google-chrome

WORKDIR /

# Fetch latest version of Chrome Driver.
RUN wget -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE`/chromedriver_linux64.zip
RUN unzip /tmp/chromedriver.zip chromedriver

# Copy required project files.
COPY *.py .
COPY Pipfile .
COPY Pipfile.lock .
COPY .env .

# Install pipenv so we can do hermetic setup.
RUN pip3.9 install pipenv
RUN pipenv install --system --deploy --ignore-pipfile



CMD ["index.lambda_handler"]