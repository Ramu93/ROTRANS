FROM python:3.9-buster

# First install wheel:
RUN python -m pip install --upgrade pip
RUN pip install wheel


RUN mkdir -p /apps
COPY . /app


RUN pip install /app/network/
RUN pip install /app/abc/
RUN pip install /app/checkpoint/

WORKDIR /app

CMD python initializr.py -cd /app/conf -ui -ep 12
