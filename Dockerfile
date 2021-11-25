FROM python:3.6

ARG VERSION
ARG BUILD_DATE

# Author
LABEL build_version="maxime1907 version:- ${VERSION} Build-date:- ${BUILD_DATE}"
LABEL maintainer="maxime1907 <maxime1907.dev@gmail.com>"

WORKDIR /home/torchlight

# Install dependencies for Torchlight
RUN apt update && apt install gpg software-properties-common -y \
    && wget -nv -O- https://dl.winehq.org/wine-builds/winehq.key | APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=1 apt-key add - \
    && apt-add-repository "deb https://dl.winehq.org/wine-builds/debian/ $(grep VERSION_CODENAME= /etc/os-release | cut -d= -f2) main" \
    && dpkg --add-architecture i386 && apt update && apt install -y youtube-dl ffmpeg xvfb wine-stable wine32

# Install winetricks
RUN wget -nv -O /usr/bin/winetricks https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks \
    && chmod +x /usr/bin/winetricks

RUN useradd -m -d /home/torchlight torchlight

# Copy base project
COPY . /home/torchlight/

# Install GeoIP
COPY ./GeoIP/GeoLite2-City.mmdb /usr/share/GeoIP/

# install python dependency
RUN pip3 install -r requirements.txt

RUN chown torchlight:torchlight -R /home/torchlight/
USER torchlight
ENTRYPOINT ["bash", "/home/torchlight/entrypoint.sh"]
