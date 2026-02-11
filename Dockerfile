# Base image with Python 3.11
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# - graphviz: For version history graph visualization
# - build-essential: For compiling Python packages
# - libgomp1: For docling dependencies
RUN apt-get update && apt-get install -y \
    graphviz \
    libgraphviz-dev \
    build-essential \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p temp /tmp/data-assistant

# Expose port (default 10000 for Render compatibility)
EXPOSE 10000

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=10000 \
    ENABLE_MCP=true \
    PYTHONDONTWRITEBYTECODE=1

# Health check using /ping endpoint (available immediately)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ping || exit 1

# Run the application
# Use uvicorn directly for better control in production
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1 --log-level info

