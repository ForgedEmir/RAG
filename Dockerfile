FROM python:3.11-slim

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY . .

EXPOSE 5000

CMD ["gunicorn", "main:app", \
     "--worker-class", "gevent", \
     "--workers", "1", \
     "--bind", "0.0.0.0:5000", \
     "--timeout", "120"]
