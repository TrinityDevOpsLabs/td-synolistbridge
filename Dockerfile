FROM python:3.12-alpine
LABEL org.opencontainers.image.title="SynoListBridge" \
      org.opencontainers.image.vendor="Trinity DevOps LLC" \
      org.opencontainers.image.licenses="Apache-2.0"
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt ./
# Alpine matches pyanylist's published x86-64 and ARM64 musllinux wheels.
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.txt \
    && addgroup -g 1000 bridge && adduser -D -u 1000 -G bridge bridge \
    && mkdir /data && chown bridge:bridge /data
COPY synolistbridge ./synolistbridge
COPY --chmod=755 bin/synolistbridge /usr/local/bin/synolistbridge
COPY LICENSE NOTICE THIRD_PARTY_NOTICES.md ./
COPY licenses ./licenses
USER 1000:1000
ENTRYPOINT ["synolistbridge"]
CMD ["run"]
