FROM python:3.11-slim as builder

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt .
COPY ml/requirements-ml.txt ./ml/requirements-ml.txt

# Install pip and package dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r ml/requirements-ml.txt && \
    # Install CPU-only version of PyTorch to save space (~150MB instead of 2GB+) and memory
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Runner stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy app code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Default command runs Django web app with Gunicorn
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2"]
