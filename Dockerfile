FROM ghcr.io/linuxserver/baseimage-ubuntu:bionic

ARG VERSION
ARG BUILD_DATE

# Author
LABEL build_version="maxime1907 version:- ${VERSION} Build-date:- ${BUILD_DATE}"
LABEL maintainer="maxime1907 <maxime1907.dev@gmail.com>"

# Install dependencies for Torchlight
RUN \
 echo "**** install runtime packages ****" && \
 dpkg --add-architecture i386 && apt update && apt install -y \
    ffmpeg \
    python3 \
    python3-pip \
    python-virtualenv \
    xvfb \
    wine-stable \
    winetricks \
    wine32 \
    nano \
    wget \
    curl \
    youtube-dl

# Copy base project
RUN mkdir -p /home/torchlight/
COPY . /home/torchlight/
RUN mv /home/torchlight/entrypoint.sh /entrypoint.sh

RUN chown -R abc:abc /home/torchlight/
RUN chmod 755 /home/torchlight

WORKDIR /home/torchlight

RUN python3 -m pip install -r /home/torchlight/requirements.txt

ENTRYPOINT ["bash", "/entrypoint.sh"]
