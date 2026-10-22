FROM python:3.12-slim-trixie@sha256:cb33f7f771ecec2ef1225cf39b159591a040391bd73e4c01f00fdfc4c47611d2 AS builder
RUN --mount=type=secret,id=build_ca,mode=0444 \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources && apt-get -o Acquire::Retries=0 -o Acquire::https::Timeout=20 -o Acquire::https::CaInfo=${SSL_CERT_FILE:-/etc/ssl/certs/ca-certificates.crt} update --error-on=any && apt-get install -y --no-install-recommends gcc python3-dev default-libmysqlclient-dev pkg-config && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
COPY requirements-university.lock /tmp/requirements.lock
RUN --mount=type=secret,id=build_ca,mode=0444 \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    /opt/venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

FROM python:3.12-slim-trixie@sha256:cb33f7f771ecec2ef1225cf39b159591a040391bd73e4c01f00fdfc4c47611d2
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DJANGO_SETTINGS_MODULE=university.production
RUN --mount=type=secret,id=build_ca,mode=0444 \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources && apt-get -o Acquire::Retries=0 -o Acquire::https::Timeout=20 -o Acquire::https::CaInfo=${SSL_CERT_FILE:-/etc/ssl/certs/ca-certificates.crt} update --error-on=any && apt-get install -y --no-install-recommends libmariadb3 libcairo2 libpango-1.0-0 libgdk-pixbuf-2.0-0 libffi8 gettext && rm -rf /var/lib/apt/lists/* && groupadd -g 10001 hr && useradd -u 10001 -g hr -M hr
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=10001:10001 . /app
RUN mkdir -p /app/media /app/staticfiles && chown 10001:10001 /app/media /app/staticfiles
ARG SOURCE_REVISION=unknown
ENV HR_SOURCE_REVISION=$SOURCE_REVISION
LABEL org.opencontainers.image.source=https://github.com/gospat/HR-Managemant org.opencontainers.image.licenses=LGPL-2.1 org.opencontainers.image.revision=$SOURCE_REVISION
USER 10001:10001
ENTRYPOINT ["sh", "/app/deploy/university/entrypoint.sh"]
CMD ["gunicorn", "horilla.wsgi:application", "--config", "deploy/university/gunicorn.conf.py"]
