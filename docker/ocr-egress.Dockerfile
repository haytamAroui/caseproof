FROM python:3.11-slim
RUN pip install --no-cache-dir pytest==8.4.2
WORKDIR /app
COPY tests/test_ocr_docker_egress.py /app/tests/test_ocr_docker_egress.py
CMD ["python", "-m", "pytest", "-q", "tests/test_ocr_docker_egress.py"]
