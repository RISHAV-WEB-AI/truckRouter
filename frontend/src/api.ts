import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

export interface RouteRequest {
  origin: string;
  destination: string;
  departure_time: string; // ISO 8601
  load_weight_lbs: number;
}

export interface Checkpoint {
  lon: number;
  lat: number;
  distance_from_start_m: number;
  eta: string;
  weather: {
    wind_mph: number;
    wind_gust_mph: number;
    rain_mm: number;
    snow_mm: number;
    condition: string;
    description: string;
    visibility_m: number;
    temp_f: number;
  };
  risk_level: number;
  risk_label: string;
  risk_color: string;
  wind_risk: number;
  rain_risk: number;
  snow_risk: number;
  vis_risk: number;
}

export interface RouteScore {
  severe_count: number;
  high_count: number;
  moderate_count: number;
  low_count: number;
  no_travel_count: number;
  avg_risk: number;
  no_travel: boolean;
}

export interface Route {
  route_index: number;
  geometry: [number, number][]; // [lon, lat]
  distance_m: number;
  duration_s: number;
  distance_miles: number;
  duration_hours: number;
  checkpoints: Checkpoint[];
  score: RouteScore;
  recommended?: boolean;
}

export interface JobResult {
  routes: Route[];
  recommended_index: number;
  origin_coords: [number, number];
  dest_coords: [number, number];
}

export interface RouteJob {
  id: number;
  task_id: string;
  origin: string;
  destination: string;
  departure_time: string;
  load_weight_lbs: number;
  status: 'pending' | 'processing' | 'done' | 'error';
  result: JobResult | { error: string } | null;
  created_at: string;
}

export async function submitRoute(data: RouteRequest): Promise<{ job_id: number; task_id: string; status: string }> {
  const res = await api.post('/route/', data);
  return res.data;
}

export async function pollJob(jobId: number): Promise<RouteJob> {
  const res = await api.get(`/route/${jobId}/`);
  return res.data;
}
