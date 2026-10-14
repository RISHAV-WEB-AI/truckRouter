import type { Route, Checkpoint, RouteScore } from './api';

const RISK_COLORS = ['#22c55e', '#eab308', '#f97316', '#ef4444', '#7c3aed'];
const RISK_LABELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel'];

export function calculateForecastCheckpoint(
  cp: Checkpoint,
  forecastHour: number,
  cpIndex: number,
  loadWeightLbs: number
): Checkpoint {
  const baseW = cp.weather || {
    wind_mph: 12,
    wind_gust_mph: 15,
    rain_mm: 0,
    snow_mm: 0,
    condition: 'Clear',
    description: 'clear sky',
    temp_f: 68,
  };

  // Simulate dynamic 48-hour weather frontal progression across the route corridor:
  // 1. Wind modulation: diurnal breeze + passing weather front around hours 12-28
  const frontProximity = Math.exp(-Math.pow((forecastHour - 18) / 8, 2));
  const corridorFactor = Math.sin((cpIndex * 0.4) + (forecastHour * 0.15));
  
  const windMph = Math.max(
    5,
    Math.round((baseW.wind_mph || 15) + (frontProximity * 28 * (0.8 + corridorFactor * 0.4)))
  );
  const windGustMph = Math.round(windMph * 1.25);

  // 2. Rain modulation (inches/hr): rain front develops between hours 14 and 32
  const rainWave = Math.max(0, Math.sin((forecastHour - 10) * 0.22) * corridorFactor);
  const rainInches = Math.max(0, Number(((baseW.rain_mm || 0) / 25.4 + (frontProximity > 0.3 ? rainWave * 0.85 : 0)).toFixed(2)));
  const rainMm = Number((rainInches * 25.4).toFixed(2));

  // 3. Snow (if temp is cold)
  const tempF = Math.round((baseW.temp_f || 65) - (forecastHour * 0.2) + Math.cos(forecastHour * 0.26) * 12);
  const snowInches = tempF < 32 && rainInches > 0.1 ? Number((rainInches * 2.5).toFixed(2)) : 0;
  const snowMm = Number((snowInches * 25.4).toFixed(2));

  // Evaluate exact prompt risk rules:
  // Wind risk & load rules
  let windRisk = 0;
  if (windMph >= 55) {
    windRisk = 4; // >=55 mph -> No Travel for any load
  } else if (windMph >= 45) {
    windRisk = loadWeightLbs > 30000 ? 4 : 3; // 45-54 mph + >30,000 lb -> No Travel, else Severe
  } else if (windMph >= 35) {
    windRisk = loadWeightLbs > 40000 ? 3 : 2; // 35-44 mph + >40,000 lb -> Severe, else High
  } else if (windMph >= 25) {
    windRisk = 1; // Moderate
  } else {
    windRisk = 0; // Low
  }

  // Rain risk (in/hr)
  let rainRisk = 0;
  if (rainInches > 1.0) rainRisk = 4;
  else if (rainInches >= 0.5) rainRisk = 3;
  else if (rainInches >= 0.25) rainRisk = 2;
  else if (rainInches >= 0.1) rainRisk = 1;

  // Snow risk (in/hr)
  let snowRisk = 0;
  if (snowInches > 3.0) snowRisk = 4;
  else if (snowInches >= 2.0) snowRisk = 3;
  else if (snowInches >= 1.0) snowRisk = 2;
  else if (snowInches >= 0.5) snowRisk = 1;

  const overall = Math.max(windRisk, rainRisk, snowRisk);
  const condition = snowInches > 0 ? 'Snow' : rainInches > 0.25 ? 'Heavy Rain' : rainInches > 0 ? 'Rain' : windMph > 35 ? 'High Winds' : 'Clear';

  return {
    ...cp,
    weather: {
      ...baseW,
      wind_mph: windMph,
      wind_gust_mph: windGustMph,
      rain_mm: rainMm,
      snow_mm: snowMm,
      condition,
      temp_f: tempF,
    },
    risk_level: overall,
    risk_label: RISK_LABELS[overall],
    risk_color: RISK_COLORS[overall],
    wind_risk: windRisk,
    rain_risk: rainRisk,
    snow_risk: snowRisk,
  };
}

export function computeForecastRoutes(
  routes: Route[],
  forecastHour: number,
  loadWeightLbs: number
): { routes: Route[]; recommendedIndex: number } {
  if (!routes || routes.length === 0) return { routes: [], recommendedIndex: 0 };

  const updatedRoutes: Route[] = routes.map(route => {
    const updatedCheckpoints = (route.checkpoints || []).map((cp, idx) =>
      calculateForecastCheckpoint(cp, forecastHour, idx, loadWeightLbs)
    );

    const levels = updatedCheckpoints.map(c => c.risk_level);
    const severeCount = levels.filter(l => l === 3).length;
    const highCount = levels.filter(l => l === 2).length;
    const moderateCount = levels.filter(l => l === 1).length;
    const lowCount = levels.filter(l => l === 0).length;
    const noTravelCount = levels.filter(l => l === 4).length;
    const avgRisk = Number((levels.reduce((a, b) => a + b, 0) / Math.max(levels.length, 1)).toFixed(2));

    const score: RouteScore = {
      severe_count: severeCount,
      high_count: highCount,
      moderate_count: moderateCount,
      low_count: lowCount,
      no_travel_count: noTravelCount,
      avg_risk: avgRisk,
      no_travel: noTravelCount > 0,
    };

    return {
      ...route,
      checkpoints: updatedCheckpoints,
      score,
      recommended: false,
    };
  });

  // Re-rank routes based on assignment hierarchy:
  // 1. Fewest Severe miles (and No Travel)
  // 2. Fewest High miles
  // 3. Lowest average risk
  // 4. Shortest travel time
  let bestIdx = 0;
  let bestScore = Infinity;

  updatedRoutes.forEach((r, idx) => {
    const s = r.score;
    // Weighted sort key strictly honoring order of preference
    const key =
      (s.no_travel_count * 1_000_000) +
      (s.severe_count * 10_000) +
      (s.high_count * 100) +
      (s.avg_risk * 10) +
      (r.duration_s / 3600);

    if (key < bestScore) {
      bestScore = key;
      bestIdx = idx;
    }
  });

  if (updatedRoutes[bestIdx]) {
    updatedRoutes[bestIdx].recommended = true;
  }

  return { routes: updatedRoutes, recommendedIndex: bestIdx };
}
