# SPDX-License-Identifier: Apache-2.0
# Installed package only; no source checkout, Task or runtime network requirement.
ARG PYTHON_IMAGE=python:3.12.12-slim-bookworm
FROM ${PYTHON_IMAGE} AS python-base

FROM ghcr.io/astral-sh/uv:0.12.23 AS uv-tools

FROM python-base AS development
COPY --from=uv-tools /uv /uvx /usr/local/bin/
ARG TASK_VERSION=3.54.0
# Debian sources use HTTPS by default (empty APT_MIRROR = https://deb.debian.org);
# the python base image already ships
# ca-certificates. APT_MIRROR replaces the deb.debian.org origin for both the
# main and security suites (e.g. https://cloudfront.debian.net behind a proxy
# that breaks deb.debian.org). Failed index downloads stop the build.
ARG APT_MIRROR=
RUN set -eu; \
    mirror="${APT_MIRROR:-https://deb.debian.org}"; \
    sed -i -E "s#^URIs: https?://deb\.debian\.org/#URIs: ${mirror%/}/#" /etc/apt/sources.list.d/debian.sources; \
    grep '^URIs:' /etc/apt/sources.list.d/debian.sources; \
    apt-get -o APT::Update::Error-Mode=any update; \
    apt-get install -y --no-install-recommends bash ca-certificates curl git dpkg-dev; \
    rm -rf /var/lib/apt/lists/*
RUN --mount=type=secret,id=ca,required=false set -eu; \
    if [ -f /run/secrets/ca ]; then export CURL_CA_BUNDLE=/run/secrets/ca; fi; \
    arch="$(dpkg --print-architecture)"; \
    mkdir /tmp/task; cd /tmp/task; \
    curl -fsSLO "https://github.com/go-task/task/releases/download/v${TASK_VERSION}/task_linux_${arch}.tar.gz"; \
    curl -fsSLO "https://github.com/go-task/task/releases/download/v${TASK_VERSION}/task_checksums.txt"; \
    sha256sum --ignore-missing -c task_checksums.txt; \
    tar -xzf "task_linux_${arch}.tar.gz" task; \
    install task /usr/local/bin/task; rm -rf /tmp/task
RUN useradd --create-home --uid 1000 --shell /bin/bash vscode
RUN mkdir -p /opt/livingproof-dev && chmod 1777 /opt/livingproof-dev
ENV UV_PROJECT_ENVIRONMENT=/opt/livingproof-dev/venv UV_CACHE_DIR=/tmp/livingproof-uv-cache
ENV PATH="/opt/livingproof-dev/venv/bin:${PATH}"
WORKDIR /workspace/livingproof
USER vscode
CMD ["sleep", "infinity"]

FROM python-base AS runtime
ARG VERSION
LABEL org.opencontainers.image.source="https://github.com/Living-Proof-Labs/livingproof"
LABEL org.opencontainers.image.version="${VERSION}"
COPY dist/wheels/ /tmp/wheels/
RUN python -m venv /opt/livingproof && /opt/livingproof/bin/pip install --no-index --find-links=/tmp/wheels "livingproof==${VERSION}" && rm -rf /tmp/wheels
ENV PATH="/opt/livingproof/bin:${PATH}"
WORKDIR /data
ENTRYPOINT ["livingproof"]
CMD ["--help"]

FROM runtime AS reporting
ARG REPORTER_VERSION
LABEL io.livingproof.reporter.version="${REPORTER_VERSION}"
COPY dist/wheels/ /tmp/wheels/
RUN /opt/livingproof/bin/pip install --no-index --find-links=/tmp/wheels "livingproof-capability-report==${REPORTER_VERSION}" && rm -rf /tmp/wheels
