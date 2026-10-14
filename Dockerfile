FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

RUN python manage.py collectstatic --noinput --settings=truckrouter.settings || true

EXPOSE 8000

CMD ["gunicorn", "truckrouter.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
