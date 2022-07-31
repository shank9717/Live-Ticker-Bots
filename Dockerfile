ARG PYTHON_VERSION=3.8.8
FROM python:${PYTHON_VERSION}

WORKDIR /usr/src/LiveTickerBot

USER root
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./ ./

CMD [ "python", "__main__.py" ]