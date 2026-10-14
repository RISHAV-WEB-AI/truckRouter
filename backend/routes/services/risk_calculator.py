"""
Weather risk classification per the exact assignment specification:

Risk Rules
Condition   Low         Moderate      High          Severe        No Travel
Wind        <25 mph     25–34         35–44         45–54         ≥55 mph
Rain        <0.10 in/hr 0.10–0.25     0.25–0.50     0.50–1.00     >1.00 in/hr
Snow        <0.5 in/hr  0.5–1.0       1.0–2.0       2.0–3.0       >3.0 in/hr

Load rules:
• ≥55 mph → No Travel for any load
• 45–54 mph + >30,000 lb → No Travel
• 35–44 mph + >40,000 lb → Severe

Route Recommendation (Preference order):
1. Fewest Severe miles (and No Travel miles)
2. Fewest High miles
3. Lowest average risk
4. Shortest travel time
"""
from typing import Any

RISK_LABELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel']
RISK_COLORS = ['#22c55e', '#eab308', '#f97316', '#ef4444', '#7c3aed']

MM_TO_INCH = 1.0 / 25.4


def classify_wind(wind_mph: float, load_lbs: float) -> int:
    """Classify wind risk including exact load rules."""
    if wind_mph >= 55.0:
        return 4  # No Travel for any load
    elif wind_mph >= 45.0:
        if load_lbs > 30000:
            return 4  # 45–54 mph + >30,000 lb → No Travel
        return 3      # Severe
    elif wind_mph >= 35.0:
        if load_lbs > 40000:
            return 3  # 35–44 mph + >40,000 lb → Severe
        return 2      # High
    elif wind_mph >= 25.0:
        return 1      # Moderate
    else:
        return 0      # Low


def classify_rain(rain_in_per_hr: float) -> int:
    """Classify rain risk in inches/hour."""
    if rain_in_per_hr > 1.00:
        return 4  # >1.00 in/hr → No Travel
    elif rain_in_per_hr >= 0.50:
        return 3  # 0.50–1.00 in/hr → Severe
    elif rain_in_per_hr >= 0.25:
        return 2  # 0.25–0.50 in/hr → High
    elif rain_in_per_hr >= 0.10:
        return 1  # 0.10–0.25 in/hr → Moderate
    else:
        return 0  # <0.10 in/hr → Low


def classify_snow(snow_in_per_hr: float) -> int:
    """Classify snow risk in inches/hour."""
    if snow_in_per_hr > 3.0:
        return 4  # >3.0 in/hr → No Travel
    elif snow_in_per_hr >= 2.0:
        return 3  # 2.0–3.0 in/hr → Severe
    elif snow_in_per_hr >= 1.0:
        return 2  # 1.0–2.0 in/hr → High
    elif snow_in_per_hr >= 0.5:
        return 1  # 0.5–1.0 in/hr → Moderate
    else:
        return 0  # <0.5 in/hr → Low


def classify_checkpoint(weather: dict[str, Any], load_lbs: float) -> dict[str, Any]:
    """
    Given weather data and load weight, return risk classification
    strictly adhering to the prompt rules.
    """
    wind_mph = float(weather.get('wind_mph', 0))

    # Support rain in inches or convert mm to inches
    if 'rain_in' in weather:
        rain_in = float(weather['rain_in'])
    else:
        rain_in = float(weather.get('rain_mm', 0)) * MM_TO_INCH

    # Support snow in inches or convert mm to inches
    if 'snow_in' in weather:
        snow_in = float(weather['snow_in'])
    else:
        snow_in = float(weather.get('snow_mm', 0)) * MM_TO_INCH

    wind_risk = classify_wind(wind_mph, load_lbs)
    rain_risk = classify_rain(rain_in)
    snow_risk = classify_snow(snow_in)

    overall = max(wind_risk, rain_risk, snow_risk)

    return {
        'risk_level': overall,
        'risk_label': RISK_LABELS[overall],
        'risk_color': RISK_COLORS[overall],
        'wind_risk': wind_risk,
        'rain_risk': rain_risk,
        'snow_risk': snow_risk,
        'rain_in': round(rain_in, 3),
        'snow_in': round(snow_in, 3),
    }


def score_route(checkpoints: list[dict], interval_miles: float = 25.0) -> dict[str, Any]:
    """
    Aggregate per-checkpoint risks into route-level score and miles:
    - severe_miles: miles under Severe risk
    - high_miles: miles under High risk
    - no_travel_miles: miles under No Travel condition
    """
    levels = [cp.get('risk_level', 0) for cp in checkpoints]
    severe_count = levels.count(3)
    high_count = levels.count(2)
    moderate_count = levels.count(1)
    low_count = levels.count(0)
    no_travel_count = levels.count(4)

    return {
        'severe_count': severe_count,
        'high_count': high_count,
        'moderate_count': moderate_count,
        'low_count': low_count,
        'no_travel_count': no_travel_count,
        'severe_miles': round(severe_count * interval_miles, 1),
        'high_miles': round(high_count * interval_miles, 1),
        'no_travel_miles': round(no_travel_count * interval_miles, 1),
        'avg_risk': round(sum(levels) / max(len(levels), 1), 2),
        'no_travel': no_travel_count > 0,
    }


def recommend_route(routes: list[dict]) -> int:
    """
    Apply assignment ranking rules strictly:
    1. Fewest Severe miles (and No Travel)
    2. Fewest High miles
    3. Lowest average risk
    4. Shortest travel time
    """
    def sort_key(indexed_route):
        _, r = indexed_route
        s = r['score']
        return (
            s.get('no_travel_count', 0),
            s.get('severe_miles', s.get('severe_count', 0)),
            s.get('high_miles', s.get('high_count', 0)),
            s.get('avg_risk', 0.0),
            r.get('duration_s', 0),
        )

    best_idx, _ = min(enumerate(routes), key=sort_key)
    return best_idx
