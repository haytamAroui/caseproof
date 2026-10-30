FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-nld tesseract-ocr-fra tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /work
