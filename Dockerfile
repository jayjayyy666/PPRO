FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Systémové balíčky nejsou potřeba: psycopg2-binary obsahuje předkompilovaný libpq.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Spuštění aplikace (uvicorn)
CMD ["uvicorn", "src.presentation.app:app", "--host", "0.0.0.0", "--port", "8000"]
