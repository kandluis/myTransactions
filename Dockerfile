ARG PYTHON_VERSION=3.10.6 

FROM amazonlinux
RUN yum update -y
RUN yum install -y \
    gcc \
    openssl-devel \
    zlib-devel \
    libffi-devel \
    wget && \
    yum -y clean all
RUN yum -y groupinstall development
WORKDIR /usr/src
# Install Python 3.10.6
RUN yum install -y tar xz
RUN wget https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tar.xz
RUN tar -xf Python-$PYTHON_VERSION.tar.xz

RUN cd Python-$PYTHON_VERSION ; ./configure --enable-optimizations; make altinstall
RUN python3.10 -V
# Install pip
RUN wget https://bootstrap.pypa.io/get-pip.py
RUN python3.10 get-pip.py
RUN rm get-pip.py
RUN pip3.10 -V

# Install pipenv and pyenv
RUN pip3.10 install pipenv
RUN curl https://pyenv.run | bash

# Install Chromedriver/Selenium
WORKDIR /opt/output/

RUN wget https://chromedriver.storage.googleapis.com/100.0.4896.20/chromedriver_linux64.zip
RUN unzip chromedriver_linux64.zip

# RUN curl -SL https://github.com/adieuadieu/serverless-chrome/releases/download/v1.0.0-57/stable-headless-chromium-amazonlinux-2.zip > headless-chromium.zip
# RUN unzip headless-chromium.zip
# RUN rm *.zip

COPY run.sh /opt/output/run.sh
ENTRYPOINT /opt/output/run.sh