FROM python:3.11-slim-bookworm

# Prevent prompts during installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

WORKDIR /app

# Install system dependencies, Chromium, and Xvfb
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    xvfb \
    curl \
    procps \
    ca-certificates \
    libglib2.0-0 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Ensure start.sh has unix line endings and execute permissions
RUN tr -d '\r' < start.sh > /tmp/start.sh && mv /tmp/start.sh start.sh && chmod +x start.sh

# Expose Render PORT (default 8080)
EXPOSE 8080

# Run entrypoint script
CMD ["./start.sh"]

