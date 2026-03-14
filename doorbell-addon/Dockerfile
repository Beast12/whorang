ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:bookworm
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
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-dev \
        python3-pip \
        curl \
        gcc \
        g++ \
        make \
        libjpeg-dev \
        zlib1g-dev \
        libffi-dev \
        pkg-config \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --break-system-packages --no-cache-dir --upgrade pip setuptools wheel
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir "insightface>=0.7.3"

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
