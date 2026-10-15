"""
OpenRouteService wrapper.
Docs: https://openrouteservice.org/dev/#/api-docs
"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

ORS_BASE = 'https://api.openrouteservice.org/v2'


_GEOCODE_CACHE: dict[str, tuple[float, float]] = {
    'chicago, il': (-87.6298, 41.8781),
    'dallas, tx': (-96.7970, 32.7767),
    'new york, ny': (-74.0060, 40.7128),
    'los angeles, ca': (-118.2437, 34.0522),
    'houston, tx': (-95.3698, 29.7604),
    'phoenix, az': (-112.0740, 33.4484),
    'philadelphia, pa': (-75.1652, 39.9526),
    'san antonio, tx': (-98.4936, 29.4241),
    'san diego, ca': (-117.1611, 32.7157),
    'denver, co': (-104.9903, 39.7392),
    'atlanta, ga': (-84.3880, 33.7490),
    'seattle, wa': (-122.3321, 47.6062),
    'miami, fl': (-80.1918, 25.7617),
    'boston, ma': (-71.0589, 42.3601),
    'detroit, mi': (-83.0458, 42.3314),
    'nashville, tn': (-86.7816, 36.1627),
    'memphis, tn': (-90.0490, 35.1495),
    'kansas city, mo': (-94.5786, 39.0997),
    'st. louis, mo': (-90.1994, 38.6270),
    'minneapolis, mn': (-93.2650, 44.9778),
    'indianapolis, in': (-86.1580, 39.7684),
    'columbus, oh': (-82.9988, 39.9612),
    'charlotte, nc': (-80.8431, 35.2271),
    'oklahoma city, ok': (-97.5164, 35.4676),
    'el paso, tx': (-106.4850, 31.7619),
    'las vegas, nv': (-115.1398, 36.1699),
    'louisville, ky': (-85.7585, 38.2527),
    'baltimore, md': (-76.6122, 39.2904),
    'albuquerque, nm': (-106.6504, 35.0844),
    'tucson, az': (-110.9747, 32.2226),
    'fresno, ca': (-119.7871, 36.7378),
    'sacramento, ca': (-121.4944, 38.5816),
    'long beach, ca': (-118.1937, 33.7701),
    'portland, or': (-122.6765, 45.5051),
    'omaha, ne': (-95.9345, 41.2524),
}


def geocode(place: str) -> tuple[float, float]:
    """
    Return (lon, lat) for a place name using:
    1. Instant memory cache
    2. Authenticated OpenRouteService Geocoding API (using ORS_API_KEY)
    3. Nominatim with custom User-Agent
    """
    clean = place.strip().lower()
    if clean in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[clean]

    # 1. Use ORS authenticated geocoding API (never rate-limited by Nominatim)
    if settings.ORS_API_KEY:
        try:
            ors_url = 'https://api.openrouteservice.org/geocode/search'
            resp = requests.get(
                ors_url,
                params={'api_key': settings.ORS_API_KEY, 'text': place, 'size': 1},
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                features = data.get('features', [])
                if features:
                    coords = features[0]['geometry']['coordinates']
                    res = (float(coords[0]), float(coords[1]))
                    _GEOCODE_CACHE[clean] = res
                    return res
        except Exception as e:
            logger.warning('ORS geocoding failed: %s', e)

    # 2. Fallback: Nominatim with custom User-Agent
    try:
        url = 'https://nominatim.openstreetmap.org/search'
        resp = requests.get(
            url,
            params={'q': place, 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'TruckRouterApp/2.0 (contact: info@spotter.ai)'},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                res = (float(data[0]['lon']), float(data[0]['lat']))
                _GEOCODE_CACHE[clean] = res
                return res
    except Exception as e:
        logger.warning('Nominatim fallback geocoding failed: %s', e)

    # 3. Direct coordinates check (e.g. "41.8781, -87.6298")
    try:
        parts = [float(x.strip()) for x in place.split(',')]
        if len(parts) == 2:
            return (parts[1], parts[0])
    except Exception:
        pass

    raise ValueError(f'Could not find coordinates for "{place}". Please enter a city and state like "Chicago, IL".')


def _request_single_route(coordinates: list[list[float]]) -> dict | None:
    url = f'{ORS_BASE}/directions/driving-hgv/geojson'
    payload = {
        'coordinates': coordinates,
        'instructions': False,
        'geometry': True,
    }
    if len(coordinates) > 2:
        # Allow intermediate waypoints to snap to nearest highway within 30km
        payload['radiuses'] = [-1] + [30000] * (len(coordinates) - 2) + [-1]

    headers = {
        'Authorization': settings.ORS_API_KEY,
        'Content-Type': 'application/json',
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
    except Exception as e:
        logger.warning('ORS request exception: %s', e)
        return None

    if resp.status_code != 200:
        logger.warning('ORS route request failed (%d): %s', resp.status_code, resp.text[:200])
        return None

    data = resp.json()
    features = data.get('features', [])
    if not features:
        return None

    feature = features[0]
    props = feature['properties']['summary']
    coords = feature['geometry']['coordinates']
    return {
        'geometry': coords,
        'distance_m': props['distance'],
        'duration_s': props['duration'],
    }


def get_routes(
    origin_coords: tuple[float, float],
    dest_coords: tuple[float, float],
    alternatives: int = 3,
) -> list[dict]:
    """
    Call ORS directions API and return up to `alternatives` route objects.
    Tries native alternative_routes first (for short routes <= 100km).
    Falls back to corridor waypoint generation for long haul truck routes.
    Always returns at least 1 route (the direct route) if ORS is reachable.
    """
    url = f'{ORS_BASE}/directions/driving-hgv/geojson'
    payload = {
        'coordinates': [list(origin_coords), list(dest_coords)],
        'alternative_routes': {
            'share_factor': 0.6,
            'target_count': alternatives,
            'weight_factor': 1.4,
        },
        'instructions': False,
        'geometry': True,
    }
    headers = {
        'Authorization': settings.ORS_API_KEY,
        'Content-Type': 'application/json',
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            routes = []
            for feature in data.get('features', []):
                props = feature['properties']['summary']
                coords = feature['geometry']['coordinates']
                routes.append({
                    'geometry': coords,
                    'distance_m': props['distance'],
                    'duration_s': props['duration'],
                })
            if routes:
                return routes
    except Exception as e:
        logger.warning('alternative_routes request failed: %s', e)

    # Fallback: Multi-corridor waypoint generation (for long-haul routes > 100km)
    routes = []

    # Primary direct route — always try this first
    primary = _request_single_route([list(origin_coords), list(dest_coords)])
    if primary:
        routes.append(primary)

    # Calculate midpoint and perpendicular offsets for alternative highway corridors
    ox, oy = origin_coords
    dx, dy = dest_coords
    mx, my = (ox + dx) / 2.0, (oy + dy) / 2.0
    vx, vy = dx - ox, dy - oy

    # Try multiple offsets — if some land in water/mountains, others should succeed
    for factor in [-0.08, 0.08, -0.12, 0.12, -0.05, 0.05]:
        if len(routes) >= alternatives:
            break
        mid_waypoint = [round(mx - factor * vy, 5), round(my + factor * vx, 5)]
        alt_route = _request_single_route([list(origin_coords), mid_waypoint, list(dest_coords)])
        if alt_route:
            # Avoid near-duplicate routes (same distance within 2%)
            is_dup = any(
                abs(r['distance_m'] - alt_route['distance_m']) / max(r['distance_m'], 1) < 0.02
                for r in routes
            )
            if not is_dup:
                routes.append(alt_route)

    if not routes:
        raise ValueError(
            f'Could not compute any route between "{origin_coords}" and "{dest_coords}". '
            'Check that ORS_API_KEY is set and both locations are reachable by road.'
        )

    return routes
