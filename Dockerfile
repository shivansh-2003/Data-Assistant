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

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create temp directory for file uploads
RUN mkdir -p temp

# Expose ports
# 8001: FastAPI (main.py)
# 8501: Streamlit (app.py)
EXPOSE 8001 8501

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Default command (can be overridden in docker-compose)
CMD ["python", "main.py"]

