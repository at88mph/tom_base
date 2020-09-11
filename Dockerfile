FROM python:3.8-slim

WORKDIR /usr/src/app

COPY . /usr/src/app

RUN apt-get update \
	&& apt-get install -y git

RUN python setup.py install
