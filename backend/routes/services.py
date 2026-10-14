import os
import requests
import time
from urllib.parse import urlencode
from .models import RouteOption, Checkpoint
from django.conf import settings

# Helper for simple retry with exponential backoff
def _request_with_retry(url, params=None, headers=None, max_retries=3, backoff_factor=1.5):
    attempt = 0
    while attempt < max_retries:
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            attempt += 1
            if attempt == max_retries:
                raise e
            time.sleep(backoff_factor ** attempt)

# Geocoding via Nominatim
def geocode(address: str):
    base = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    data = _request_with_retry(base, params=params, headers={"User-Agent": "truckrouter/1.0"})
    if not data:
        raise ValueError(f"Could not geocode address: {address}")
    return float(data[0]["lat"]), float(data[0]["lon"])  # lat, lon

# Routing via OpenRouteService
def get_routes(origin: tuple, destination: tuple):
    api_key = os.getenv("OPENROUTESERVICE_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENROUTESERVICE_API_KEY not set in .env")
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": api_key, "Accept": "application/json", "Content-Type": "application/json"}
    coords = [[origin[1], origin[0]], [destination[1], destination[0]]]  # lon, lat order
    payload = {"coordinates": coords, "options": {"alternatives": 3}}
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    # Return list of encoded polylines (ORS provides geometry in GeoJSON; we convert to polyline via 'geometry' and 'coordinates')
    routes = []
    for feature in data.get("features", []):
        # geometry is a list of [lon, lat] pairs
        coords_list = feature["geometry"]["coordinates"]
        # Encode to polyline using simple joining (frontend will decode via polyline library)
        # Here we store as a JSON string of coordinates for simplicity
        routes.append(coords_list)
    return routes

# Decode polyline / coordinate list (here it's already a list of lon/lat)
def decode_coords(coord_list):
    # Convert list of [lon, lat] to list of (lat, lon)
    return [(c[1], c[0]) for c in coord_list]

# Sample checkpoints every N miles (approximate conversion: 1 mile ≈ 1.60934 km)
def sample_checkpoints(coords, interval_miles=10):
    # Simple linear sampling based on index proportion – for demo purposes.
    if not coords:
        return []
    total_points = len(coords)
    interval_km = interval_miles * 1.60934
    # Approximate total distance using haversine would be better; here we just take every Nth point.
    step = max(1, int(total_points * interval_km / 100))  # rough heuristic
    sampled = []
    for i in range(0, total_points, step):
        lat, lon = decode_coords([coords[i]])[0]
        sampled.append((lat, lon, i))  # include index as mile marker proxy
    return sampled

# Weather fetching from OpenWeatherMap (One Call API)
def fetch_weather(lat, lon, dt_timestamp):
    api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENWEATHERMAP_API_KEY not set in .env")
    url = "https://api.openweathermap.org/data/2.5/onecall/timemachine"
    params = {
        "lat": lat,
        "lon": lon,
        "dt": dt_timestamp,
        "appid": api_key,
        "units": "imperial",
    }
    data = _request_with_retry(url, params=params)
    # Return relevant fields; OpenWeatherMap returns hourly data – we take the first hour
    hourly = data.get("hourly", [{}])[0]
    return {
        "wind_mph": hourly.get("wind_speed"),
        "rain_in_per_hr": hourly.get("rain", {}).get("1h", 0),
        "snow_in_per_hr": hourly.get("snow", {}).get("1h", 0),
    }

# Risk calculation based on the provided thresholds and load rules
def calculate_risk(weather: dict, load_weight: int, speed_mph: float):
    # Wind risk
    wind = weather.get("wind_mph", 0)
    if wind > 20:
        wind_risk = "Severe"
    elif wind > 15:
        wind_risk = "High"
    elif wind > 10:
        wind_risk = "Moderate"
    else:
        wind_risk = "Low"
    # Rain risk (convert inches to mm: 1 in = 25.4 mm)
    rain_mm = weather.get("rain_in_per_hr", 0) * 25.4
    if rain_mm > 15:
        rain_risk = "Severe"
    elif rain_mm > 10:
        rain_risk = "High"
    elif rain_mm > 5:
        rain_risk = "Moderate"
    else:
        rain_risk = "Low"
    # Snow risk (1 in = 25.4 mm)
    snow_mm = weather.get("snow_in_per_hr", 0) * 25.4
    if snow_mm > 10:
        snow_risk = "Severe"
    elif snow_mm > 5:
        snow_risk = "High"
    else:
        snow_risk = "Low"
    # Combine risks – pick the highest severity
    severity_order = ["Low", "Moderate", "High", "Severe"]
    combined = max([wind_risk, rain_risk, snow_risk], key=lambda r: severity_order.index(r))
    # Load rules adjustments (simplified – actual rule set would be more detailed)
    # Example: if load > 40000 lbs and speed > 55 mph, downgrade risk by one level
    if load_weight > 40000 and speed_mph > 55 and combined != "Low":
        idx = severity_order.index(combined)
        combined = severity_order[max(0, idx - 1)]
    return combined

# Recommendation ordering – placeholder simple sort by avg risk score (lower is better)
def recommend_route(options):
    # Assume options already have computed risk metrics
    # Sort by (severity, total_time, total_distance)
    severity_rank = {"Low": 0, "Moderate": 1, "High": 2, "Severe": 3}
    def sort_key(opt):
        # Use avg_risk_score (0‑3) derived from severity levels
        return (
            opt.avg_risk_score,
            opt.total_time_min,
            opt.total_distance_km,
        )
    sorted_opts = sorted(options, key=sort_key)
    # Mark first as recommended
    for i, opt in enumerate(sorted_opts):
        opt.is_recommended = (i == 0)
        opt.save()
    return sorted_opts[0] if sorted_opts else None
