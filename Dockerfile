FROM python:3.11-slim

WORKDIR /app

# Install deps first so we cache them across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source.
COPY nanda ./nanda
COPY services ./services
COPY scripts ./scripts
COPY frontend ./frontend

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default command is overridden per service in docker-compose.yml.
CMD ["python", "-c", "print('Specify a service via docker-compose')"]
