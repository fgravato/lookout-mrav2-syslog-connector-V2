# MRAv2 Syslog Connector - Docker Image
# Multi-stage build for smaller production image

FROM python:3.9-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.9-slim

# Create non-root user for security
RUN groupadd -r lookout && useradd -r -g lookout lookout

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY lookout_mra_client/ ./lookout_mra_client/
COPY setup.py .
COPY README.md .
COPY LICENSE .

# Install the package
RUN pip install --no-cache-dir -e .

# Create log directory
RUN mkdir -p /app/logs && chown -R lookout:lookout /app

# Switch to non-root user
USER lookout

# Expose no ports (outbound connections only)
# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "mrav2-syslog-connector" || exit 1

# Default command (requires config to be mounted)
ENTRYPOINT ["mrav2-syslog-connector"]
CMD ["--config", "/app/config.ini", "--log-file", "/app/logs/connector.log"]
