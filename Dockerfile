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

# Third-party runtime assets are fetched and verified in a throwaway stage so the
# runtime image does not need curl. To bump one, update its version ARG and set
# the matching *_SHA256 to the `sha256sum` of the new download.
FROM build as assets

# GeoLite2 City DB, redistributed as an immutable npm package by
# wp-statistics/GeoLite2-City (old versions stay downloadable, unlike rotating
# GitHub release tags).
ARG GEOLITE2_CITY_VERSION=1.0.107
ARG GEOLITE2_CITY_SHA256=832eebcfc88a4fb151b348e70d27c4d8c3c5cc5fb593d2852ec9982949174a25
ARG DECTALK_VERSION=2023-10-30
ARG DECTALK_SHA256=185d94dbb5f51f6f866a4d4521b39eba486095753d21d398578cc573604e3b0c

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /tmp/assets

RUN curl -fsSL --retry 3 \
        "https://registry.npmjs.org/geolite2-city/-/geolite2-city-${GEOLITE2_CITY_VERSION}.tgz" \
        -o geolite2-city.tgz \
    && echo "${GEOLITE2_CITY_SHA256}  geolite2-city.tgz" | sha256sum -c - \
    && mkdir -p /out/GeoIP \
    && tar -xzOf geolite2-city.tgz package/GeoLite2-City.mmdb.gz | gunzip > /out/GeoIP/GeoLite2-City.mmdb \
    && rm -f geolite2-city.tgz

RUN curl -fsSL --retry 3 \
        "https://github.com/dectalk/dectalk/releases/download/${DECTALK_VERSION}/ubuntu-latest.tar.gz" \
        -o dectalk.tar.gz \
    && echo "${DECTALK_SHA256}  dectalk.tar.gz" | sha256sum -c - \
    && mkdir -p dectalk /out/dectalk \
    && tar -xzf dectalk.tar.gz -C dectalk --strip-components=1 --no-same-owner \
    && mv dectalk/say /out/dectalk \
    && mv dectalk/dic/* /out/dectalk \
    && mv dectalk/lib /out/dectalk \
    && rm -rf dectalk.tar.gz dectalk

FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 as runtime

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG DEBIAN_FRONTEND=noninteractive

# hadolint ignore=DL3008
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update -yq \
    && apt-get install -yq --no-install-recommends \
    ca-certificates \
    ffmpeg \
    libmagic1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/log/*

COPY --from=assets /out/GeoIP/ /usr/share/GeoIP/
COPY --from=assets /out/dectalk/ /opt/dectalk/

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
