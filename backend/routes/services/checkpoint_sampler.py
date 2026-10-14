"""
Sample checkpoint coordinates along a route at specified mile intervals.
"""
import math
from datetime import datetime, timedelta
from typing import Any

METRES_PER_MILE = 1609.344


def haversine_m(a: list[float], b: list[float]) -> float:
    """Return distance in metres between two [lon, lat] points."""
    R = 6_371_000
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a_ = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a_))


def sample_checkpoints(
    geometry: list[list[float]],
    distance_m: float,
    duration_s: float,
    departure_dt: datetime,
    interval_miles: int = 25,
) -> list[dict[str, Any]]:
    """
    Walk the route geometry and emit a checkpoint every `interval_miles`.
    Returns a list of dicts:
      { lon, lat, distance_from_start_m, eta (ISO string) }
    """
    interval_m = interval_miles * METRES_PER_MILE
    speed_mps = distance_m / max(duration_s, 1)  # metres per second

    checkpoints = []
    accumulated = 0.0
    next_threshold = interval_m

    # Always include origin
    checkpoints.append({
        'lon': geometry[0][0],
        'lat': geometry[0][1],
        'distance_from_start_m': 0,
        'eta': departure_dt.isoformat(),
    })

    for i in range(1, len(geometry)):
        seg_dist = haversine_m(geometry[i - 1], geometry[i])
        accumulated += seg_dist

        while accumulated >= next_threshold:
            # Interpolate exactly at the threshold
            excess = accumulated - next_threshold
            frac = 1 - (excess / seg_dist) if seg_dist > 0 else 0.5
            lon = geometry[i - 1][0] + frac * (geometry[i][0] - geometry[i - 1][0])
            lat = geometry[i - 1][1] + frac * (geometry[i][1] - geometry[i - 1][1])
            travel_s = next_threshold / speed_mps
            eta = departure_dt + timedelta(seconds=travel_s)
            checkpoints.append({
                'lon': lon,
                'lat': lat,
                'distance_from_start_m': next_threshold,
                'eta': eta.isoformat(),
            })
            next_threshold += interval_m

    # Always include destination
    checkpoints.append({
        'lon': geometry[-1][0],
        'lat': geometry[-1][1],
        'distance_from_start_m': distance_m,
        'eta': (departure_dt + timedelta(seconds=duration_s)).isoformat(),
    })

    return checkpoints
