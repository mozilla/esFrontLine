FROM python:2.7-alpine

ADD . /frontline
COPY tests/docker/frontline.json /etc/frontline.json

RUN pip install /frontline

ENV PYTHONPATH "/frontline/vendor"

CMD esFrontLine --settings-file /etc/frontline.json
