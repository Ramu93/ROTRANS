FROM python:3.9-buster

WORKDIR /code

ENV FLASK_ENV development

ENV ZMQ_SERVER_SOCKET agent

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt 

EXPOSE 5000

COPY . .

CMD ["python", "src/main.py"]
