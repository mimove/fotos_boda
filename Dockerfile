FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY download_models.py .
RUN python download_models.py
COPY app.py index_photos.py face_engine.py start_app.sh ./
COPY licenses licenses
COPY templates templates
COPY static static
RUN useradd --uid 1000 --create-home app
ENV PHOTO_ROOT=/photos DATA_DIR=/data
USER app
EXPOSE 5000
CMD ["sh", "start_app.sh"]
