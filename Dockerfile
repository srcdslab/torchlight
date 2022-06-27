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

## !yt FIX (Cmer)
RUN wget https://yt-dl.org/downloads/latest/youtube-dl -O /usr/local/bin/youtube-dl \
    && chmod a+rx /usr/local/bin/youtube-dl

# Install winetricks
RUN wget -nv -O /usr/bin/winetricks https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks \
    && chmod +x /usr/bin/winetricks

# set UUID and GUID for Pterodactyl 
RUN groupadd -g 998 -o torchlight
RUN useradd -m -u 999 -g 998 -d /home/torchlight torchlight

# Copy base project
COPY . /home/torchlight/

# Install GeoIP
COPY ./GeoIP/GeoLite2-City.mmdb /usr/share/GeoIP/

# install python dependency
RUN pip3 install -r requirements.txt

RUN chown torchlight:torchlight -R /home/torchlight/ -R
USER torchlight
ENTRYPOINT ["bash", "/home/torchlight/entrypoint.sh"]
