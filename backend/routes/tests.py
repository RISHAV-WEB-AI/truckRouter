from django.test import TestCase
from routes.services.risk_calculator import classify_checkpoint, score_route, recommend_route


class ExactRiskRulesTests(TestCase):
    def _weather(self, wind=0, rain_in=0, snow_in=0):
        return {
            'wind_mph': wind,
            'rain_in': rain_in,
            'snow_in': snow_in,
            'condition': 'Clear',
            'description': '',
            'temp_f': 65,
        }

    # 1. Base wind tests
    def test_wind_thresholds_light_load(self):
        # <25 Low, 25-34 Moderate, 35-44 High, 45-54 Severe, >=55 No Travel
        self.assertEqual(classify_checkpoint(self._weather(wind=20), 10000)['risk_level'], 0)  # Low
        self.assertEqual(classify_checkpoint(self._weather(wind=30), 10000)['risk_level'], 1)  # Moderate
        self.assertEqual(classify_checkpoint(self._weather(wind=40), 10000)['risk_level'], 2)  # High
        self.assertEqual(classify_checkpoint(self._weather(wind=50), 10000)['risk_level'], 3)  # Severe
        self.assertEqual(classify_checkpoint(self._weather(wind=55), 10000)['risk_level'], 4)  # No Travel

    # 2. Exact load rules
    def test_load_rule_ge_55_no_travel_any_load(self):
        # >=55 mph -> No Travel for any load
        self.assertEqual(classify_checkpoint(self._weather(wind=55), 5000)['risk_label'], 'No Travel')
        self.assertEqual(classify_checkpoint(self._weather(wind=60), 60000)['risk_label'], 'No Travel')

    def test_load_rule_45_to_54_plus_over_30k_lb(self):
        # 45–54 mph + >30,000 lb → No Travel
        # 45–54 mph with <=30,000 lb is Severe
        normal = classify_checkpoint(self._weather(wind=48), 28000)
        heavy = classify_checkpoint(self._weather(wind=48), 35000)
        self.assertEqual(normal['risk_label'], 'Severe')
        self.assertEqual(heavy['risk_label'], 'No Travel')

    def test_load_rule_35_to_44_plus_over_40k_lb(self):
        # 35–44 mph + >40,000 lb → Severe
        # 35–44 mph with <=40,000 lb is High
        normal = classify_checkpoint(self._weather(wind=38), 35000)
        heavy = classify_checkpoint(self._weather(wind=38), 45000)
        self.assertEqual(normal['risk_label'], 'High')
        self.assertEqual(heavy['risk_label'], 'Severe')

    # 3. Rain thresholds
    def test_rain_thresholds(self):
        # <0.10 Low, 0.10–0.25 Moderate, 0.25–0.50 High, 0.50–1.00 Severe, >1.00 No Travel
        self.assertEqual(classify_checkpoint(self._weather(rain_in=0.05), 10000)['risk_level'], 0)
        self.assertEqual(classify_checkpoint(self._weather(rain_in=0.15), 10000)['risk_level'], 1)
        self.assertEqual(classify_checkpoint(self._weather(rain_in=0.35), 10000)['risk_level'], 2)
        self.assertEqual(classify_checkpoint(self._weather(rain_in=0.75), 10000)['risk_level'], 3)
        self.assertEqual(classify_checkpoint(self._weather(rain_in=1.20), 10000)['risk_level'], 4)

    # 4. Snow thresholds
    def test_snow_thresholds(self):
        # <0.5 Low, 0.5–1.0 Moderate, 1.0–2.0 High, 2.0–3.0 Severe, >3.0 No Travel
        self.assertEqual(classify_checkpoint(self._weather(snow_in=0.2), 10000)['risk_level'], 0)
        self.assertEqual(classify_checkpoint(self._weather(snow_in=0.8), 10000)['risk_level'], 1)
        self.assertEqual(classify_checkpoint(self._weather(snow_in=1.5), 10000)['risk_level'], 2)
        self.assertEqual(classify_checkpoint(self._weather(snow_in=2.5), 10000)['risk_level'], 3)
        self.assertEqual(classify_checkpoint(self._weather(snow_in=3.5), 10000)['risk_level'], 4)

    # 5. Recommendation hierarchy
    def test_recommendation_fewest_severe_miles(self):
        # Prefer fewest severe miles
        routes = [
            {'score': {'no_travel_count': 0, 'severe_miles': 50.0, 'high_miles': 0.0, 'avg_risk': 1.8}, 'duration_s': 3600},
            {'score': {'no_travel_count': 0, 'severe_miles': 0.0, 'high_miles': 100.0, 'avg_risk': 1.5}, 'duration_s': 4000},
        ]
        self.assertEqual(recommend_route(routes), 1)

    def test_recommendation_fewest_high_miles(self):
        # Tied on severe miles -> prefer fewest high miles
        routes = [
            {'score': {'no_travel_count': 0, 'severe_miles': 0.0, 'high_miles': 75.0, 'avg_risk': 1.2}, 'duration_s': 3600},
            {'score': {'no_travel_count': 0, 'severe_miles': 0.0, 'high_miles': 25.0, 'avg_risk': 1.0}, 'duration_s': 3800},
        ]
        self.assertEqual(recommend_route(routes), 1)

    def test_recommendation_lowest_avg_risk(self):
        # Tied on severe and high -> prefer lowest average risk
        routes = [
            {'score': {'no_travel_count': 0, 'severe_miles': 0.0, 'high_miles': 0.0, 'avg_risk': 0.8}, 'duration_s': 3600},
            {'score': {'no_travel_count': 0, 'severe_miles': 0.0, 'high_miles': 0.0, 'avg_risk': 0.2}, 'duration_s': 3700},
        ]
        self.assertEqual(recommend_route(routes), 1)

    def test_recommendation_shortest_time(self):
        # Tied on all risk metrics -> prefer shortest travel time
        routes = [
            {'score': {'no_travel_count': 0, 'severe_miles': 0.0, 'high_miles': 0.0, 'avg_risk': 0.2}, 'duration_s': 4000},
            {'score': {'no_travel_count': 0, 'severe_miles': 0.0, 'high_miles': 0.0, 'avg_risk': 0.2}, 'duration_s': 3200},
        ]
        self.assertEqual(recommend_route(routes), 1)
