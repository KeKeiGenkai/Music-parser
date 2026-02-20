
FROM rust:1-bookworm AS librespot-builder
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch v0.8.0 https://github.com/librespot-org/librespot.git /src && \
    cd /src && \
    cargo build --release --locked --no-default-features --features "native-tls"

FROM python:3.12-slim-bookworm

RUN rm -rf /var/lib/apt/lists/* \
    && apt-get update \
    && apt-get install -y --no-install-recommends --fix-missing ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=librespot-builder /src/target/release/librespot /usr/local/bin/

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY parsers ./parsers
COPY recorder ./recorder
COPY run_record.py web.py ./

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["sleep", "infinity"]
