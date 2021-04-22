FROM aminfa/abc-network:latest

RUN mkdir -p /apps/abc-core
COPY ./requirements.module.txt /app/abc-core/requirements.module.txt

RUN pip install -r /app/abc-core/requirements.module.txt

COPY . /app/abc-core/
WORKDIR /app/abc-core/

COPY conf /app/conf

CMD python initializr.py -cd /app/conf -ui -ep 12
