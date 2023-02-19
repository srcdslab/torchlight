FROM ubuntu:20.04

RUN DEBIAN_FRONTEND=noninteractive apt update -y && apt install -y libmagic-dev ffmpeg python3 python3-pip curl --no-install-recommends

WORKDIR /app

# youtube-dl
RUN curl -L https://github.com/ytdl-patched/youtube-dl/releases/latest/download/youtube-dl -o /usr/local/bin/youtube-dl \
    && chmod a+rx /usr/local/bin/youtube-dl \
    && ln -s /usr/bin/python3 /usr/bin/python

# DecTalk
RUN curl -L https://github.com/dectalk/dectalk/releases/download/2022-09-15/linux-amd64.tar.gz -o /tmp/dectalk.tar.gz \
    && mkdir -p /app/dectalk \
    && tar -xvf /tmp/dectalk.tar.gz -C /app/dectalk --strip-components=1 \
    && rm -rf /tmp/dectalk.tar.gz

COPY . /app

RUN pip install --no-cache-dir --prefer-binary .

COPY GeoIP/GeoLite2-City.mmdb /usr/share/GeoIP/

ENTRYPOINT ["torchlight"]
