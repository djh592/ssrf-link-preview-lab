FROM python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641

RUN apt-get update \
    && apt-get install --yes --no-install-recommends unbound \
    && rm -rf /var/lib/apt/lists/*

COPY docker/unbound.conf.template /etc/unbound/unbound.conf.template
COPY docker/run_resolver.py /usr/local/bin/run_resolver.py

CMD ["python", "/usr/local/bin/run_resolver.py"]
