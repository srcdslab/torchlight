# syntax=docker/dockerfile:1.6@sha256:ac85f380a63b13dfcefa89046420e1781752bab202122f8f50032edf31be0021

FROM python:3.12-bookworm@sha256:581429e3df12d76e6af4be5ab7d0e7fc2013eb57dc23d2de691411c8efdbb970 as build

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

FROM build as build-common

COPY src/ ./src/

RUN --mount=type=secret,id=pipconf,dst="/root/.config/pip/pip.conf" \
    --mount=type=cache,sharing=locked,id=pipcache,mode=0777,target=/root/.cache/pip/http \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=VERSION,target=VERSION \
    python -m build --sdist

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

FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 as runtime

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
    && curl -L https://github.com/P3TERX/GeoLite.mmdb/releases/download/2026.03.25/GeoLite2-City.mmdb -o /usr/share/GeoIP/GeoLite2-City.mmdb

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
    pip install --no-cache-dir --no-compile --prefer-binary /wheels/*

RUN --mount=type=bind,from=build-common,source=/app/dist,target=/dist \
    pip install --no-cache-dir --no-compile --prefer-binary /dist/*

USER rootless

COPY --chown=rootless:rootless config/ /app/config
COPY --chown=rootless:rootless sounds/ /app/sounds

FROM runtime as production

USER root

RUN --mount=type=bind,from=build-production,source=/app/wheels,target=/wheels \
    pip install --no-cache-dir --no-compile --prefer-binary /wheels/*

RUN --mount=type=bind,from=build-common,source=/app/dist,target=/dist \
    pip install --no-cache-dir --no-compile --prefer-binary /dist/*

USER rootless

COPY --chown=rootless:rootless config/ /app/config
COPY --chown=rootless:rootless sounds/ /app/sounds
COPY --chown=rootless:rootless ./entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
