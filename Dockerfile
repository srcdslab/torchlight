# syntax=docker/dockerfile:1.6@sha256:ac85f380a63b13dfcefa89046420e1781752bab202122f8f50032edf31be0021

FROM python:3.10-bookworm@sha256:4f7ca582d310c40d430ab6a17c46a0b360aee5987e0ef5aa155eeabc9ffa8393 as build

ARG BUILD_VERSION=0.10.0

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update -yq \
    && apt-get install -yq --no-install-recommends \
    build-essential=12.9 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/log/*

# hadolint ignore=DL3042
RUN --mount=type=cache,sharing=locked,id=pipcache,mode=0777,target=/root/.cache/pip/http \
    pip install --no-compile build==$BUILD_VERSION

FROM build as build-production

# hadolint ignore=DL3042
RUN --mount=type=secret,id=pipconf,dst="/root/.config/pip/pip.conf" \
    --mount=type=cache,sharing=locked,id=pipcache,mode=0777,target=/root/.cache/pip/http \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    pip wheel --no-deps --wheel-dir /app/wheels -r requirements.txt

COPY src/ ./src/

RUN --mount=type=secret,id=pipconf,dst="/root/.config/pip/pip.conf" \
    --mount=type=cache,sharing=locked,id=pipcache,mode=0777,target=/root/.cache/pip/http \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=VERSION,target=VERSION \
    python -m build --sdist

FROM build as build-development

# hadolint ignore=DL3042
RUN --mount=type=secret,id=pipconf,dst="/root/.config/pip/pip.conf" \
    --mount=type=cache,sharing=locked,id=pipcache,mode=0777,target=/root/.cache/pip/http \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    --mount=type=bind,source=requirements-dev.txt,target=requirements-dev.txt \
    pip wheel --no-deps --wheel-dir /app/wheels -r requirements.txt -r requirements-dev.txt \

COPY src/ ./src/

RUN --mount=type=secret,id=pipconf,dst="/root/.config/pip/pip.conf" \
    --mount=type=cache,sharing=locked,id=pipcache,mode=0777,target=/root/.cache/pip/http \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=VERSION,target=VERSION \
    python -m build --sdist

FROM python:3.10-slim-bookworm@sha256:9a97ede5d731252b42541a5d3ec60f6d4cd03747ca75315adc784ed864651c0e as runtime

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND noninteractive

# hadolint ignore=DL3008
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

RUN mkdir -p /usr/share/GeoIP/ \
    && curl -L https://github.com/P3TERX/GeoLite.mmdb/releases/download/2024.02.16/GeoLite2-City.mmdb -o /usr/share/GeoIP/GeoLite2-City.mmdb

RUN curl -L https://github.com/dectalk/dectalk/releases/download/2023-10-30/ubuntu-latest.tar.gz -o /tmp/dectalk.tar.gz \
    && mkdir -p /tmp/dectalk /opt/dectalk \
    && tar -xvf /tmp/dectalk.tar.gz -C /tmp/dectalk --strip-components=1 \
    && mv /tmp/dectalk/say /opt/dectalk \
    && mv /tmp/dectalk/dic/* /opt/dectalk \
    && mv /tmp/dectalk/lib /opt/dectalk \
    && rm -rf /tmp/dectalk.tar.gz /tmp/dectalk

RUN groupadd -g 1000 rootless && \
    useradd --create-home -r -u 1000 -g rootless rootless

USER rootless

WORKDIR /app

ENV PATH="/home/rootless/.local/bin:/opt/dectalk:${PATH}"

FROM runtime as development

USER root

RUN --mount=type=bind,from=build-development,source=/app/wheels,target=/wheels \
    --mount=type=bind,from=build-development,source=/app/dist,target=/dist \
    pip install --no-cache-dir --no-compile --prefer-binary /wheels/* \
    && pip install --no-cache-dir --no-compile --prefer-binary /dist/*

USER rootless

COPY --chown=rootless:rootless config/ /app/config
COPY --chown=rootless:rootless sounds/ /app/sounds

FROM runtime as production

USER root

RUN --mount=type=bind,from=build-production,source=/app/wheels,target=/wheels \
    --mount=type=bind,from=build-production,source=/app/dist,target=/dist \
    pip install --no-cache-dir --no-compile --prefer-binary /wheels/* \
    && pip install --no-cache-dir --no-compile --prefer-binary /dist/*

USER rootless

COPY --chown=rootless:rootless config/ /app/config
COPY --chown=rootless:rootless sounds/ /app/sounds

ENTRYPOINT ["torchlight"]
