FROM python:3.11-slim

WORKDIR /app

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install all dependencies including CPU-only PyTorch
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port for Cloud Run
EXPOSE 8080

# Start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
