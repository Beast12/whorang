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
        curl \
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

# Install dlib with conservative CPU flags to avoid AVX/SSE4 crashes on virtualized CPUs
RUN set -eux; \
    DLIB_VERSION=19.24.2; \
    if [ "$(uname -m)" = "x86_64" ]; then \
        echo "Building dlib for AMD64 without AVX/SSE4 for virtualization compatibility..."; \
        DLIB_CPU_FLAGS="-O2 -pipe -mno-avx -mno-avx2 -mno-sse4.1 -mno-sse4.2 -mno-fma -march=x86-64 -mtune=generic"; \
        curl -L "https://files.pythonhosted.org/packages/source/d/dlib/dlib-${DLIB_VERSION}.tar.gz" -o /tmp/dlib.tar.gz; \
        tar -xzf /tmp/dlib.tar.gz -C /tmp; \
        cd "/tmp/dlib-${DLIB_VERSION}"; \
        python3 setup.py install \
            --no USE_AVX_INSTRUCTIONS \
            --no USE_SSE4_INSTRUCTIONS \
            --set USE_SSE2_INSTRUCTIONS=ON \
            --set DLIB_USE_BLAS=ON \
            --set DLIB_USE_LAPACK=ON \
            --set CMAKE_C_FLAGS="${DLIB_CPU_FLAGS}" \
            --set CMAKE_CXX_FLAGS="${DLIB_CPU_FLAGS}"; \
        cd /; \
        rm -rf "/tmp/dlib-${DLIB_VERSION}" /tmp/dlib.tar.gz; \
    else \
        echo "Building dlib for $(uname -m) with default flags..."; \
        pip3 install --no-cache-dir --no-binary :all: --no-build-isolation "dlib==${DLIB_VERSION}"; \
    fi

# Verify dlib loads successfully and report AVX status
RUN python3 -c "import dlib; print('✓ dlib loaded successfully; AVX enabled:', getattr(dlib, 'USE_AVX_INSTRUCTIONS', None))"

# Install face-recognition (will use system opencv via py3-opencv)
RUN pip3 install --no-cache-dir face-recognition

# Install system OpenCV and Pillow AFTER pip packages to avoid metadata conflicts during pip install
# The malformed opencv metadata won't affect already-installed pip packages
RUN apk add --no-cache py3-opencv py3-pillow

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
