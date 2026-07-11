# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY python ./python
COPY specs ./specs
RUN python -m pip wheel --wheel-dir /wheels ".[api,production]"

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    URP_REPO_ROOT=/opt/urp
RUN groupadd --system --gid 10001 urp \
    && useradd --system --uid 10001 --gid urp --home-dir /var/lib/urp urp \
    && mkdir -p /var/lib/urp/.urp /opt/urp \
    && chown -R urp:urp /var/lib/urp
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels urp \
    && rm -rf /wheels
COPY --chown=root:root specs /opt/urp/specs
COPY --chown=root:root deployments /opt/urp/deployments
COPY --chown=root:root examples/policies /opt/urp/examples/policies

USER 10001:10001
WORKDIR /var/lib/urp
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/readyz', timeout=2).read()"]
ENTRYPOINT ["python", "-m", "urp.cli", "--state-dir", "/var/lib/urp/.urp"]
CMD ["service", "run", "--name", "control-plane", "--listen", "0.0.0.0:8080"]
