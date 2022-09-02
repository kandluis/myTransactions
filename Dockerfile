FROM public.ecr.aws/lambda/python:3.9

RUN yum update -y
RUN yum install -y \
    git \
    unzip \
    wget && \
    yum -y clean all

# Install pipenv and pyenv
RUN pip3.9 install pipenv
RUN curl https://pyenv.run | bash

# Install Chromedriver/Selenium
WORKDIR /opt/output/

RUN wget https://chromedriver.storage.googleapis.com/100.0.4896.20/chromedriver_linux64.zip
RUN unzip chromedriver_linux64.zip

COPY run.sh /opt/output/run.sh
ENTRYPOINT /opt/output/run.sh