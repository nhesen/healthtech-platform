FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY demo_documents ./demo_documents
RUN mkdir -p /app/uploads /data

EXPOSE 8000
CMD ["sh", "-c", "python -m app.migrate && python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
