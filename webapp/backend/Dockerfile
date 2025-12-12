FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Chrome and ChromeDriver
RUN apt-get update && \
    apt-get install -y \
    gcc \
    postgresql-client \
    wget \
    gnupg \
    unzip \
    chromium \
    chromium-driver && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
