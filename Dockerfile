# ── Stage 1: Build React Frontend ─────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python / Django Production Server ───────────
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

# Copy built React frontend into Django app directory
COPY --from=frontend-builder /frontend/dist /app/frontend_dist

# Collect static files
RUN python manage.py collectstatic --noinput --settings=truckrouter.settings || true

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn truckrouter.wsgi:application --bind 0.0.0.0:8000 --workers 2"]
