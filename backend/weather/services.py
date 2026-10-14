"""
OpenWeatherMap API wrapper supporting OneCall 3.0 and Free 2.5 Forecast fallback.
"""
import time
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

OWM_ONECALL_BASE = 'https://api.openweathermap.org/data/3.0/onecall'
OWM_FORECAST_BASE = 'https://api.openweathermap.org/data/2.5/forecast'

_cache: dict = {}
CACHE_TTL = 600  # 10 minutes

_last_401_time: float = 0
DISABLE_AFTER_401_SECS = 30  # Don't hammer failing API key repeatedly


def _cache_key(lat: float, lon: float, dt: int) -> str:
    # Round to ~1km grid + nearest hour to maximise cache hits
    return f'{round(lat, 2)},{round(lon, 2)},{dt // 3600}'


def _fetch_onecall(lat: float, lon: float, unix_timestamp: int, now: float) -> dict | None:
    global _last_401_time
    if now - _last_401_time < DISABLE_AFTER_401_SECS:
        return None

    params = {
        'lat': lat,
        'lon': lon,
        'appid': settings.OPENWEATHER_API_KEY,
        'units': 'imperial',
        'exclude': 'minutely,alerts',
    }
    hours_diff = (unix_timestamp - now) / 3600
    if -1 <= hours_diff <= 48:
        url = OWM_ONECALL_BASE
    else:
        url = f'{OWM_ONECALL_BASE}/timemachine'
        params['dt'] = unix_timestamp

    try:
        resp = requests.get(url, params=params, timeout=2.5)
        if resp.status_code == 401:
            _last_401_time = now
            return None
        if resp.status_code != 200:
            return None

        raw = resp.json()
        hourly = raw.get('hourly', [raw.get('data', [{}])[0]])
        best = min(hourly, key=lambda h: abs(h.get('dt', 0) - unix_timestamp))

        wind_mph = best.get('wind_speed', 0)
        wind_gust_mph = best.get('wind_gust', wind_mph)
        rain_mm = best.get('rain', {}).get('1h', 0)
        snow_mm = best.get('snow', {}).get('1h', 0)
        weather_main = best.get('weather', [{}])[0].get('main', 'Clear')
        description = best.get('weather', [{}])[0].get('description', '')
        visibility_m = best.get('visibility', 10000)
        temp_f = best.get('temp', 70)

        return {
            'wind_mph': round(wind_mph, 1),
            'wind_gust_mph': round(wind_gust_mph, 1),
            'rain_mm': round(rain_mm, 2),
            'snow_mm': round(snow_mm, 2),
            'condition': weather_main,
            'description': description,
            'visibility_m': visibility_m,
            'temp_f': round(temp_f, 1),
        }
    except Exception as e:
        logger.debug('OneCall fetch exception: %s', e)
        return None


def _fetch_free_forecast(lat: float, lon: float, unix_timestamp: int, now: float) -> dict | None:
    """Fallback to standard Free 5-day / 3-hour forecast API."""
    global _last_401_time
    if now - _last_401_time < DISABLE_AFTER_401_SECS:
        return None

    params = {
        'lat': lat,
        'lon': lon,
        'appid': settings.OPENWEATHER_API_KEY,
        'units': 'imperial',
    }
    try:
        resp = requests.get(OWM_FORECAST_BASE, params=params, timeout=2.5)
        if resp.status_code == 401:
            _last_401_time = now
            return None
        if resp.status_code != 200:
            return None

        data = resp.json()
        items = data.get('list', [])
        if not items:
            return None

        best = min(items, key=lambda h: abs(h.get('dt', 0) - unix_timestamp))

        wind_mph = best.get('wind', {}).get('speed', 0)
        wind_gust_mph = best.get('wind', {}).get('gust', wind_mph)
        rain_mm = best.get('rain', {}).get('3h', 0) / 3.0  # normalize to mm/hr
        snow_mm = best.get('snow', {}).get('3h', 0) / 3.0
        weather_main = best.get('weather', [{}])[0].get('main', 'Clear')
        description = best.get('weather', [{}])[0].get('description', '')
        visibility_m = best.get('visibility', 10000)
        temp_f = best.get('main', {}).get('temp', 70)

        return {
            'wind_mph': round(wind_mph, 1),
            'wind_gust_mph': round(wind_gust_mph, 1),
            'rain_mm': round(rain_mm, 2),
            'snow_mm': round(snow_mm, 2),
            'condition': weather_main,
            'description': description,
            'visibility_m': visibility_m,
            'temp_f': round(temp_f, 1),
        }
    except Exception as e:
        logger.debug('Free forecast fetch exception: %s', e)
        return None


def get_weather_at(
    lat: float,
    lon: float,
    unix_timestamp: int,
) -> dict:
    """
    Return weather data for (lat, lon) at the given UNIX timestamp.
    Tries OneCall 3.0 first, then falls back to Free 2.5 5-day forecast.
    """
    key = _cache_key(lat, lon, unix_timestamp)
    now = time.time()
    if key in _cache and now - _cache[key]['ts'] < CACHE_TTL:
        return _cache[key]['data']

    # 1. Try OneCall 3.0
    result = _fetch_onecall(lat, lon, unix_timestamp, now)

    # 2. Try Free 2.5 Forecast if OneCall unavailable
    if result is None:
        result = _fetch_free_forecast(lat, lon, unix_timestamp, now)

    # 3. Default fallback if API key still activating or network error
    if result is None:
        result = {
            'wind_mph': 12.0,
            'wind_gust_mph': 15.0,
            'rain_mm': 0.0,
            'snow_mm': 0.0,
            'condition': 'Clear',
            'description': 'clear sky',
            'visibility_m': 10000,
            'temp_f': 68.0,
        }

    _cache[key] = {'ts': now, 'data': result}
    return result
