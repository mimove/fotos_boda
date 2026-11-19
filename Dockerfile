FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake libopenblas-dev liblapack-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py index_photos.py ./
COPY templates templates
COPY static static
RUN useradd --uid 1000 --create-home app
ENV PHOTO_ROOT=/photos DATA_DIR=/data
USER app
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "--workers", "2", "app:app"]
