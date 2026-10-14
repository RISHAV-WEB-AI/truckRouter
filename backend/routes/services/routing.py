"""
OpenRouteService wrapper.
Docs: https://openrouteservice.org/dev/#/api-docs
"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

ORS_BASE = 'https://api.openrouteservice.org/v2'


def geocode(place: str) -> tuple[float, float]:
    """Return (lon, lat) for a place name using Nominatim."""
    url = 'https://nominatim.openstreetmap.org/search'
    resp = requests.get(
        url,
        params={'q': place, 'format': 'json', 'limit': 1},
        headers={'User-Agent': 'TruckRouter/1.0'},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f'Could not geocode: {place}')
    return float(data[0]['lon']), float(data[0]['lat'])


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
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
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

    # Fallback: Multi-corridor waypoint generation (for long-haul routes > 100km)
    routes = []
    # Primary direct route
    primary = _request_single_route([list(origin_coords), list(dest_coords)])
    if primary:
        routes.append(primary)

    # Calculate midpoint and perpendicular offsets for alternative highway corridors
    ox, oy = origin_coords
    dx, dy = dest_coords
    mx, my = (ox + dx) / 2.0, (oy + dy) / 2.0
    vx, vy = dx - ox, dy - oy

    # Corridors 2 and 3 with snapping radii
    for factor in [-0.08, 0.08]:
        mid_waypoint = [round(mx - factor * vy, 5), round(my + factor * vx, 5)]
        alt_route = _request_single_route([list(origin_coords), mid_waypoint, list(dest_coords)])
        if alt_route:
            routes.append(alt_route)

    if not routes:
        raise ValueError('Unable to compute any valid routes between origin and destination.')

    return routes
