# syntax=docker/dockerfile:1.6@sha256:ac85f380a63b13dfcefa89046420e1781752bab202122f8f50032edf31be0021

FROM python:3.10-bookworm@sha256:4f7ca582d310c40d430ab6a17c46a0b360aee5987e0ef5aa155eeabc9ffa8393 as build

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update -yq \
    && apt-get install -yq --no-install-recommends \
    build-essential=12.9 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/log/*

FROM build as build-production

# hadolint ignore=DL3042
RUN --mount=type=secret,id=pipconf,dst="/root/.config/pip/pip.conf" \
    --mount=type=cache,sharing=locked,id=pipcache,mode=0777,target=/root/.cache/pip/http \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    pip wheel --no-deps --wheel-dir /app/wheels -r requirements.txt

FROM build as build-development

# hadolint ignore=DL3042
RUN --mount=type=secret,id=pipconf,dst="/root/.config/pip/pip.conf" \
    --mount=type=cache,sharing=locked,id=pipcache,mode=0777,target=/root/.cache/pip/http \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    --mount=type=bind,source=requirements-dev.txt,target=requirements-dev.txt \
    pip wheel --no-deps --wheel-dir /app/wheels -r requirements.txt -r requirements-dev.txt

FROM python:3.10-slim-bookworm@sha256:9a97ede5d731252b42541a5d3ec60f6d4cd03747ca75315adc784ed864651c0e as runtime

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND noninteractive

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update -yq \
    && apt-get install -yq --no-install-recommends \
    curl \
    ffmpeg \
    git \
    libmagic-dev \
    software-properties-common \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/log/* \
    && update-ca-certificates

# GeoIP2
RUN mkdir -p /usr/share/GeoIP/ \
    && curl -L https://git.io/GeoLite2-City.mmdb -o /usr/share/GeoIP/GeoLite2-City.mmdb

RUN groupadd -g 1000 rootless && \
    useradd --create-home -r -u 1000 -g rootless rootless

USER rootless

WORKDIR /app

ENV PATH="/home/rootless/.local/bin:${PATH}"

# DecTalk
RUN curl -L https://github.com/dectalk/dectalk/releases/download/2022-09-15/linux-amd64.tar.gz -o /tmp/dectalk.tar.gz \
    && mkdir -p /app/dectalk \
    && tar -xvf /tmp/dectalk.tar.gz -C /app/dectalk --strip-components=1 \
    && rm -rf /tmp/dectalk.tar.gz

FROM runtime as development

COPY --chown=rootless:rootless . .

RUN --mount=type=bind,from=build-development,source=/app/wheels,target=/wheels \
    pip install --no-cache-dir --no-compile --prefer-binary /wheels/* \
    && pip install --no-cache-dir --no-compile --prefer-binary -e .

FROM runtime as production

COPY --chown=rootless:rootless . .

RUN --mount=type=bind,from=build-production,source=/app/wheels,target=/wheels \
    pip install --no-cache-dir --no-compile --prefer-binary /wheels/* \
    && pip install --no-cache-dir --no-compile --prefer-binary -e .

ENTRYPOINT ["torchlight"]
