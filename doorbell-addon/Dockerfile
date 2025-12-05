ARG BUILD_FROM=ghcr.io/hassio-addons/base/amd64:18.1.0
FROM $BUILD_FROM

# Build arguments
ARG DOORBELL_VERSION
ARG TARGETARCH

# Labels
LABEL \
    io.hass.name="Doorbell Face Recognition" \
    io.hass.description="AI-powered doorbell with face recognition capabilities" \
    io.hass.arch="${TARGETARCH}" \
    io.hass.type="addon" \
    io.hass.version=${DOORBELL_VERSION} \
    maintainer="Beast12" \
    org.opencontainers.image.title="Doorbell Face Recognition" \
    org.opencontainers.image.description="AI-powered doorbell with face recognition capabilities" \
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
        py3-numpy \
        gcc \
        g++ \
        make \
        cmake \
        linux-headers \
        musl-dev \
        jpeg-dev \
        zlib-dev \
        libffi-dev \
        pkgconfig \
        ffmpeg \
        ffmpeg-dev \
        gstreamer \
        gst-plugins-base \
        gst-plugins-good \
        gst-plugins-bad \
        gst-plugins-ugly \
        gst-libav \
        blas-dev \
        lapack-dev \
        gfortran \
        openblas-dev

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# Use uvicorn without [standard] for ARM builds to avoid Rust compilation issues
RUN pip3 install --no-cache-dir fastapi uvicorn jinja2 python-multipart
RUN pip3 install --no-cache-dir sqlalchemy httpx aiofiles python-dateutil
RUN pip3 install --no-cache-dir paho-mqtt requests pydantic pydantic-settings structlog
RUN pip3 install --no-cache-dir "cryptography>=42.0.0" "passlib[bcrypt]"

# Install Pillow and OpenCV via pip (avoid Alpine py3-opencv metadata conflicts)
RUN pip3 install --no-cache-dir Pillow opencv-python-headless==4.9.0.80

# Install dlib with CPU compatibility flags for Proxmox/QEMU
# Force compilation from source with explicit CPU flags to disable AVX/SSE4
# Using --no-binary to ensure we compile from source, not use pre-built wheels
RUN echo "Building dlib from source without AVX/SSE4 for Proxmox/QEMU compatibility..." && \
    export CFLAGS="-O2 -mno-avx -mno-avx2 -mno-sse4.1 -mno-sse4.2 -mno-fma -march=x86-64 -mtune=generic" && \
    export CXXFLAGS="-O2 -mno-avx -mno-avx2 -mno-sse4.1 -mno-sse4.2 -mno-fma -march=x86-64 -mtune=generic" && \
    pip3 install --no-cache-dir --no-binary :all: --no-build-isolation dlib==19.24.2

# Verify dlib loads without illegal instructions
RUN python3 -c "import dlib; print('✓ dlib loaded successfully without AVX/SSE4')"

# Install face-recognition
RUN pip3 install --no-cache-dir face-recognition

# Copy application code
COPY src/ ./src/
COPY web/ ./web/
COPY run.sh .

# Make run script executable
RUN chmod +x run.sh

# Create necessary directories
RUN mkdir -p /data/doorbell /data/faces /data/images

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8099/health || exit 1

# Expose port
EXPOSE 8099

# Start script
CMD ["./run.sh"]
