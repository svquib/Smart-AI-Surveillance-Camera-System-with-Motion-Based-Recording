# Backend image: FastAPI + the vision libs.
# Note: this serves the API/DB-backed side. The webcam pipeline still runs on
# the host — Docker Desktop on macOS can't reach the Mac camera (see README).

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# OpenCV needs libGL/glib at runtime; ffmpeg is our clip transcode fallback.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install deps first so this layer caches when only app code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
