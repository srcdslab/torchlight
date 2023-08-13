FROM python:3.10-slim

RUN DEBIAN_FRONTEND=noninteractive apt update -y && apt install -y git libmagic-dev ffmpeg curl software-properties-common --no-install-recommends

WORKDIR /app

# DecTalk
RUN curl -L https://github.com/dectalk/dectalk/releases/download/2022-09-15/linux-amd64.tar.gz -o /tmp/dectalk.tar.gz \
    && mkdir -p /app/dectalk \
    && tar -xvf /tmp/dectalk.tar.gz -C /app/dectalk --strip-components=1 \
    && rm -rf /tmp/dectalk.tar.gz

# GeoIP2
RUN mkdir -p /usr/share/GeoIP/ \
    && curl -L https://git.io/GeoLite2-City.mmdb -o /usr/share/GeoIP/GeoLite2-City.mmdb

COPY requirements.txt /app/requirements.txt

RUN pip install -r requirements.txt

COPY . /app

RUN pip install --no-cache-dir --prefer-binary .

ENTRYPOINT ["torchlight"]
