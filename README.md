# 🚛 TruckRouter — Weather-Aware Safe Routing

A full-stack web application designed for commercial truck dispatchers and heavy-haul drivers to find the safest, most efficient driving routes based on real-time weather forecasts, truck load weight, and travel time.

---

## 🌟 Key Features

1. **Multi-Route Generation**: Fetches up to 3 distinct Heavy Goods Vehicle (HGV) highway corridors between origin and destination using the **OpenRouteService** API.
2. **Adaptive Checkpoint Weather Sampling**:
   - Calculates estimated arrival time (ETA) for every checkpoint along the route based on truck speed and departure schedule.
   - Dynamic sampling intervals: **10 miles** (<100 mi), **25 miles** (100–500 mi), or **50 miles** (>500 mi).
3. **Weight-Aware Weather Risk Classification**:
   - **Wind Thresholds**: `<25 mph` (Low), `25–34 mph` (Moderate), `35–44 mph` (High), `45–54 mph` (Severe), `≥55 mph` (No Travel).
   - **Load Rule 1**: `≥55 mph` → **No Travel** for any load.
   - **Load Rule 2**: `45–54 mph` + `>30,000 lb` → **No Travel**.
   - **Load Rule 3**: `35–44 mph` + `>40,000 lb` → **Severe**.
   - **Rain Thresholds**: `<0.10 in/hr` (Low), `0.10–0.25` (Mod), `0.25–0.50` (High), `0.50–1.00` (Severe), `>1.00` (No Travel).
   - **Snow Thresholds**: `<0.5 in/hr` (Low), `0.5–1.0` (Mod), `1.0–2.0` (High), `2.0–3.0` (Severe), `>3.0` (No Travel).
4. **Hierarchical Route Recommendation**:
   - Automatically ranks and selects the safest route using strict multi-tier criteria:
     1. Fewest **Severe miles** & No Travel miles
     2. Fewest **High miles**
     3. Lowest **average risk**
     4. Shortest **travel time**
5. **Interactive Map & Visuals**:
   - Built with **Leaflet** featuring colored polyline corridors, risk-coded checkpoint circles with detailed weather popups, and route summary cards.
6. **Corridor Weather Heatmap & 0–48 Hour Forecast Slider**:
   - Interactive slider dynamically updates the corridor heatmap, checkpoint risk markers, arrival ETAs, and route rankings in real time across a 48-hour horizon.

---

## 🏗 Architecture & Tech Stack

- **Frontend**: React 18, TypeScript, Vite, Leaflet, `leaflet.heat`, CSS Design Tokens.
- **Backend**: Python 3.11+, Django 5.0, Django REST Framework, WhiteNoise.
- **Asynchronous Processing**: Celery with Redis broker (with seamless resilient background thread dispatch for lightweight environments).
- **External APIs**:
  - OpenRouteService (HGV Driving Profile)
  - Nominatim OpenStreetMap (Geocoding)
  - OpenWeatherMap (Forecast & Weather data)

---

## 🚀 Local Setup Instructions

### 1. Prerequisites
- Python 3.11 or higher
- Node.js 18 or higher
- Git

### 2. Clone and Configure Environment
```bash
git clone <repository-url>
cd spotter
```

Create `backend/.env` with your API keys:
```env
DJANGO_SECRET_KEY=dev-secret-key-change-in-production
DEBUG=True
ALLOWED_HOSTS=*
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
ORS_API_KEY=<your-openrouteservice-key>
OPENWEATHER_API_KEY=<your-openweathermap-key>
```

### 3. Backend Setup
```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py test routes   # Runs the 10/10 risk rule test suite
python manage.py runserver
```

### 4. Frontend Setup
In a second terminal:
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## 🧪 Testing

Run the automated test suite covering all risk threshold rules, load escalations, and recommendation sorting:
```bash
cd backend
venv\Scripts\python manage.py test routes --verbosity=2
```

---

## ☁️ Deployment on Render

This repository includes a production-ready `Dockerfile` and `render.yaml` blueprint:

1. Push this repository to GitHub.
2. In [Render Dashboard](https://dashboard.render.com/), click **New** ➔ **Blueprint**.
3. Connect your GitHub repository.
4. Render will automatically set up:
   - **Web Service** (`Dockerfile` + Gunicorn)
   - **Celery Worker** (`celery -A truckrouter worker`)
   - **Redis Instance**
   - **PostgreSQL Database**
5. Under Environment Variables in Render, provide your `ORS_API_KEY` and `OPENWEATHER_API_KEY`.
