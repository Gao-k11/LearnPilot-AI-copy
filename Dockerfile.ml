FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY ml/requirements.txt /app/ml/requirements.txt
COPY ml/requirements-advanced.txt /app/ml/requirements-advanced.txt
RUN pip install --no-cache-dir -r /app/ml/requirements.txt -r /app/ml/requirements-advanced.txt

COPY ml /app/ml

ENV PYTHONPATH=/app/ml/src
CMD ["uvicorn", "ml_service.api:app", "--app-dir", "ml/src", "--host", "0.0.0.0", "--port", "8000"]
