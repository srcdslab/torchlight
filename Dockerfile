FROM ghcr.io/linuxserver/docker-baseimage-alpine:3.14

ARG VERSION
ARG BUILD_DATE

# Author
LABEL build_version="maxime1907 version:- ${VERSION} Build-date:- ${BUILD_DATE}"
LABEL maintainer="maxime1907 <maxime1907.dev@gmail.com>"

# Install dependencies for Torchlight
RUN \
 echo "**** install runtime packages ****" && \
 apk add --no-cache --upgrade \
    ca-certificates \
    ffmpeg \
    python3.6 \
    python-virtualenv \
    xvfb \
    wine \
    wine32 \
    nano \
    wget \
    curl \
    wine \
    winetricks \
    youtube-dl

# Copy base project
RUN mkdir -p /home/torchlight/
COPY . /home/torchlight/
RUN mv /home/torchlight/entrypoint.sh /entrypoint.sh

RUN chown -R abc:abc /home/torchlight/
RUN chmod 755 /home/torchlight

WORKDIR /home/torchlight

RUN pip install -r /home/torchlight/requirements.txt

#ENV PATH=$PATH:/home/torchlight:/home/torchlight/.local/bin:/root/.local/bin

ENTRYPOINT ["bash", "/entrypoint.sh"]
