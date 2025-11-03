# Use a small multi-arch image (works fine on Intel & Apple Silicon)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app (main.py, .env, etc.)
COPY . .

# Expose uvicorn port
EXPOSE 8000

# Start FastAPI with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
