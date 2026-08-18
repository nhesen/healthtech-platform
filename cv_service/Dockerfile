FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY app ./app
COPY run_demo.py .

CMD ["python", "run_demo.py", "--simulate"]
