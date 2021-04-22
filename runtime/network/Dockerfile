FROM python:3.9-buster

RUN mkdir -p /apps/network

RUN python -m pip install --upgrade pip
RUN pip install wheel

COPY abcnet /app/network/abcnet
COPY setup.py /app/network

RUN pip install /app/network/

CMD python -m
