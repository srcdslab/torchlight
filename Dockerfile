FROM ubuntu:20.04

RUN DEBIAN_FRONTEND=noninteractive apt update -y && apt install -y libmagic-dev ffmpeg curl software-properties-common --no-install-recommends \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt install -y python3.10 python3.10-distutils --no-install-recommends \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3.10

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

COPY GeoIP/GeoLite2-City.mmdb /usr/share/GeoIP/

COPY requirements.txt /app/requirements.txt

RUN python3.10 -m pip install -r requirements.txt

COPY . /app

RUN python3.10 -m pip install --no-cache-dir --prefer-binary .

ENTRYPOINT ["torchlight"]
