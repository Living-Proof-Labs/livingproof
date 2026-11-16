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
# Behind a TLS-intercepting proxy, the optional BuildKit secret `ca` (the same one
# the Task download uses) is appended to the system bundle for apt only, in a
# temporary file that is removed before the layer is written. Readable by _apt,
# which runs the HTTPS downloads. Without the secret apt runs unchanged.
ARG APT_MIRROR=
RUN --mount=type=secret,id=ca,required=false set -eu; \
    apt_ca=; bundle=; \
    if [ -s /run/secrets/ca ]; then \
      bundle="$(mktemp)"; \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/ca > "$bundle"; \
      chmod 644 "$bundle"; \
      apt_ca="-o Acquire::https::CAInfo=$bundle"; \
    fi; \
    mirror="${APT_MIRROR:-https://deb.debian.org}"; \
    sed -i -E "s#^URIs: https?://deb\.debian\.org/#URIs: ${mirror%/}/#" /etc/apt/sources.list.d/debian.sources; \
    grep '^URIs:' /etc/apt/sources.list.d/debian.sources; \
    apt-get $apt_ca -o APT::Update::Error-Mode=any update; \
    apt-get $apt_ca install -y --no-install-recommends bash ca-certificates curl git dpkg-dev; \
    rm -f "$bundle"; \
    rm -rf /var/lib/apt/lists/*
# Runtime certificate for uv, git and Python builds. Exported only when the
# mounted PEM contains a certificate. The mount is outside the system
# certificate directory. This is separate from the BuildKit secret `ca`, which
# applies only to the image build (apt above and the Task download below).
COPY docker/dev-ca-env.sh docker/dev-entrypoint.sh /usr/local/bin/
COPY docker/livingproof-ca.sh /etc/profile.d/livingproof-ca.sh
RUN chmod 755 /usr/local/bin/dev-ca-env.sh /usr/local/bin/dev-entrypoint.sh \
 && chmod 644 /etc/profile.d/livingproof-ca.sh
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
RUN mkdir -p /opt/livingproof-dev /run/livingproof \
 && chmod 1777 /opt/livingproof-dev && chmod 755 /run/livingproof
ENV UV_PROJECT_ENVIRONMENT=/opt/livingproof-dev/venv UV_CACHE_DIR=/tmp/livingproof-uv-cache
ENV PATH="/opt/livingproof-dev/venv/bin:${PATH}"
WORKDIR /workspace/livingproof
USER vscode
ENTRYPOINT ["/usr/local/bin/dev-entrypoint.sh"]
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
