FROM python:3.10-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

COPY apps/api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
