FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model (best effort; do not fail the image build if unavailable)
RUN python -m spacy download en_core_web_sm || true

# Download TextBlob corpora (best effort; do not fail the image build if unavailable)
RUN python -m textblob.download_corpora || true

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p uploads

# Cloud Run uses PORT env variable (default to 8000)
ENV PORT=8000

# Expose port
EXPOSE 8000

# Run the application (read PORT from environment for Cloud Run compatibility)
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --reload"
