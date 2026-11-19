FROM python:3.11-slim

# Install system dependencies including FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port 8000
EXPOSE 8000

ENV HOST=127.0.0.1
ENV PORT=8000

# Run entrypoint
CMD ["python", "run.py"]
