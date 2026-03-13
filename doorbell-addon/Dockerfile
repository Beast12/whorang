ARG BUILD_FROM=ghcr.io/hassio-addons/base/amd64:18.1.0
FROM $BUILD_FROM

# Build arguments
ARG DOORBELL_VERSION
ARG TARGETARCH

# Labels
LABEL \
    io.hass.name="WhoRang Doorbell" \
    io.hass.description="Doorbell event history with image capture and weather integration" \
    io.hass.arch="${TARGETARCH}" \
    io.hass.type="addon" \
    io.hass.version=${DOORBELL_VERSION} \
    maintainer="Beast12" \
    org.opencontainers.image.title="WhoRang Doorbell" \
    org.opencontainers.image.description="Doorbell event history with image capture and weather integration" \
    org.opencontainers.image.version=${DOORBELL_VERSION} \
    org.opencontainers.image.source="https://github.com/Beast12/whorang" \
    org.opencontainers.image.authors="Beast12" \
    org.opencontainers.image.licenses="MIT"

# Install system dependencies
RUN \
    apk add --no-cache \
        python3 \
        python3-dev \
        py3-pip \
        curl \
        gcc \
        g++ \
        make \
        musl-dev \
        jpeg-dev \
        zlib-dev \
        libffi-dev \
        pkgconfig \
        ffmpeg \
        py3-pillow \
        gcompat \
        libstdc++

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY web/ ./web/
COPY run.sh .

# Make run script executable
RUN chmod +x run.sh

# Model persistence path
ENV INSIGHTFACE_HOME=/data/insightface_models

# Create necessary directories
RUN mkdir -p /data/doorbell /data/images /data/insightface_models

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8099/health || exit 1

# Expose port
EXPOSE 8099

# Start script
CMD ["./run.sh"]
