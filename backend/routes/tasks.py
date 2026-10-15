from celery import shared_task
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import logging

from .models import RouteJob
from .services.routing import geocode, get_routes
from .services.checkpoint_sampler import sample_checkpoints
from .services.risk_calculator import classify_checkpoint, score_route, recommend_route
from weather.services import get_weather_at

logger = logging.getLogger(__name__)

INTERVAL_MAP = {
    'short':  10,   # < 100 miles
    'medium': 25,   # 100–500 miles
    'long':   50,   # > 500 miles
}
METRES_PER_MILE = 1609.344


def run_compute_routes(job_id: int):
    """
    Core logic for computing routes, shared by both Celery task and thread fallback.
    """
    try:
        job = RouteJob.objects.get(id=job_id)
        job.status = 'processing'
        job.save(update_fields=['status'])

        # 1. Geocode
        origin_coords = geocode(job.origin)
        dest_coords   = geocode(job.destination)

        # 2. Routes
        raw_routes = get_routes(origin_coords, dest_coords, alternatives=3)

        departure_dt = job.departure_time
        if departure_dt.tzinfo is None:
            departure_dt = departure_dt.replace(tzinfo=timezone.utc)

        enriched_routes = []
        for idx, route in enumerate(raw_routes):
            distance_miles = route['distance_m'] / METRES_PER_MILE

            # 3. Pick sampling interval
            if distance_miles < 100:
                interval = INTERVAL_MAP['short']
            elif distance_miles < 500:
                interval = INTERVAL_MAP['medium']
            else:
                interval = INTERVAL_MAP['long']

            checkpoints = sample_checkpoints(
                geometry=route['geometry'],
                distance_m=route['distance_m'],
                duration_s=route['duration_s'],
                departure_dt=departure_dt,
                interval_miles=interval,
            )

            # 4. Weather + risk at each checkpoint (concurrently)
            def _enrich_single(cp):
                try:
                    eta_ts = int(datetime.fromisoformat(cp['eta']).timestamp())
                    weather = get_weather_at(cp['lat'], cp['lon'], eta_ts)
                    risk = classify_checkpoint(weather, job.load_weight_lbs)
                except Exception as e:
                    logger.warning('Weather fetch failed for checkpoint: %s', e)
                    weather = {}
                    risk = {'risk_level': 0, 'risk_label': 'Low', 'risk_color': '#22c55e',
                            'wind_risk': 0, 'rain_risk': 0, 'snow_risk': 0, 'vis_risk': 0}
                return {**cp, 'weather': weather, **risk}

            with ThreadPoolExecutor(max_workers=10) as executor:
                enriched_checkpoints = list(executor.map(_enrich_single, checkpoints))

            route_score = score_route(enriched_checkpoints)

            enriched_routes.append({
                'route_index': idx,
                'geometry': route['geometry'],
                'distance_m': route['distance_m'],
                'duration_s': route['duration_s'],
                'distance_miles': round(distance_miles, 1),
                'duration_hours': round(route['duration_s'] / 3600, 2),
                'checkpoints': enriched_checkpoints,
                'score': route_score,
            })

        # 5. Recommend
        recommended_idx = recommend_route(enriched_routes)
        enriched_routes[recommended_idx]['recommended'] = True

        # 6. Save
        job.result = {
            'routes': enriched_routes,
            'recommended_index': recommended_idx,
            'origin_coords': origin_coords,
            'dest_coords': dest_coords,
        }
        job.status = 'done'
        job.save(update_fields=['status', 'result'])

    except Exception as exc:
        logger.exception('compute_routes failed for job %s', job_id)
        try:
            job = RouteJob.objects.get(id=job_id)
            job.status = 'error'
            job.result = {'error': str(exc)}
            job.save(update_fields=['status', 'result'])
        except Exception:
            pass


@shared_task(bind=True, max_retries=2)
def compute_routes(self, job_id: int):
    """Celery task wrapper — calls run_compute_routes, retries on failure."""
    try:
        run_compute_routes(job_id)
    except Exception as exc:
        logger.exception('Celery compute_routes task failed for job %s', job_id)
        raise self.retry(exc=exc, countdown=15)
