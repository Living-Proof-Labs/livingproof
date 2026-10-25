# SPDX-License-Identifier: Apache-2.0
# Installed package only; no source checkout, Task or runtime network requirement.
ARG PYTHON_IMAGE=python:3.12.12-slim-bookworm
FROM ${PYTHON_IMAGE} AS python-base

FROM ghcr.io/astral-sh/uv:0.12.23 AS uv-tools

FROM python-base AS development
COPY --from=uv-tools /uv /uvx /usr/local/bin/
ARG TASK_VERSION=3.54.0
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates curl git && rm -rf /var/lib/apt/lists/*
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
ENV UV_PROJECT_ENVIRONMENT=/tmp/livingproof-venv UV_CACHE_DIR=/tmp/livingproof-uv-cache
WORKDIR /workspace/livingproof
USER vscode
CMD ["sleep", "infinity"]
