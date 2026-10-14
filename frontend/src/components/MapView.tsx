import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Route, Checkpoint, JobResult } from '../api';

// Attach L to window so leaflet.heat can hook into it
if (typeof window !== 'undefined') {
  (window as any).L = L;
}
import 'leaflet.heat';

// Fix default marker icons broken by Vite bundling
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const ROUTE_COLORS = ['#3b82f6', '#a855f7', '#f59e0b'];
const RISK_COLORS  = ['#22c55e', '#eab308', '#f97316', '#ef4444', '#7c3aed'];
const RISK_LABELS  = ['Low', 'Moderate', 'High', 'Severe', 'No Travel'];

interface Props {
  result: JobResult | null;
  selectedRoute: number | null;
  forecastHour: number;
}

function riskCircleStyle(level: number) {
  const safeLevel = Math.max(0, Math.min(4, Math.round(level || 0)));
  const isHighRisk = safeLevel >= 3;
  return {
    radius: isHighRisk ? 9 : 7,
    fillColor: RISK_COLORS[safeLevel] ?? '#22c55e',
    color: '#0a0f1e',
    weight: isHighRisk ? 3 : 2,
    opacity: 1,
    fillOpacity: 0.95,
  };
}

function buildPopupHtml(cp: Checkpoint, forecastHour: number): string {
  const w = cp.weather ?? {};
  const safeLevel = Math.max(0, Math.min(4, Math.round(cp.risk_level || 0)));
  const color = cp.risk_color ?? RISK_COLORS[safeLevel] ?? '#22c55e';
  const rawDate = cp.eta ? new Date(cp.eta) : new Date();
  const adjustedDate = new Date(rawDate.getTime() + forecastHour * 3600 * 1000);
  const eta = adjustedDate.toLocaleString();
  const dist = ((cp.distance_from_start_m || 0) / 1609.344).toFixed(1);
  const rainIn = w.rain_mm != null ? (w.rain_mm / 25.4).toFixed(2) : '0.00';
  const snowIn = w.snow_mm != null ? (w.snow_mm / 25.4).toFixed(2) : '0.00';

  return `
    <div style="font-family:Inter,sans-serif;min-width:210px;background:#1e293b;color:#f1f5f9;border-radius:8px;padding:10px;">
      <div style="display:inline-block;background:${color}22;color:${color};font-size:0.7rem;font-weight:700;
                  padding:2px 8px;border-radius:10px;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;">
        ${RISK_LABELS[safeLevel] ?? 'Unknown'} Risk
      </div>
      <div style="font-size:0.75rem;color:#94a3b8;margin-bottom:3px;"><b style="color:#f1f5f9">📍 Mile</b> ${dist} mi</div>
      <div style="font-size:0.75rem;color:#94a3b8;margin-bottom:3px;"><b style="color:#f1f5f9">🕐 ETA</b> ${eta} ${forecastHour > 0 ? `(+${forecastHour}h)` : ''}</div>
      ${w.wind_mph != null ? `<div style="font-size:0.75rem;color:#94a3b8;margin-bottom:3px;"><b style="color:#f1f5f9">💨 Wind</b> ${w.wind_mph} mph (gusts ${w.wind_gust_mph ?? w.wind_mph} mph)</div>` : ''}
      <div style="font-size:0.75rem;color:#94a3b8;margin-bottom:3px;"><b style="color:#f1f5f9">🌧 Rain</b> ${rainIn} in/hr</div>
      ${Number(snowIn) > 0 ? `<div style="font-size:0.75rem;color:#94a3b8;margin-bottom:3px;"><b style="color:#f1f5f9">❄️ Snow</b> ${snowIn} in/hr</div>` : ''}
      ${w.temp_f != null ? `<div style="font-size:0.75rem;color:#94a3b8;"><b style="color:#f1f5f9">🌡 Temp</b> ${w.temp_f}°F</div>` : ''}
    </div>
  `;
}

export default function MapView({ result, selectedRoute, forecastHour }: Props) {
  const mapRef       = useRef<L.Map | null>(null);
  const divRef       = useRef<HTMLDivElement>(null);
  const layerRef     = useRef<L.LayerGroup | null>(null);
  const heatRef      = useRef<any>(null);
  const lastFitIdRef = useRef<string | null>(null);

  // ── Init map ──────────────────────────────────────────
  useEffect(() => {
    if (!divRef.current || mapRef.current) return;
    try {
      const map = L.map(divRef.current, {
        center: [39.5, -98.35],
        zoom: 4,
        zoomControl: true,
      });

      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20,
      }).addTo(map);

      layerRef.current = L.layerGroup().addTo(map);
      mapRef.current   = map;
    } catch (e) {
      console.error('Failed to initialize map:', e);
    }

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  // ── Render routes & checkpoints ───────────────────────
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    try {
      layer.clearLayers();
      if (heatRef.current) {
        try { map.removeLayer(heatRef.current); } catch {}
        heatRef.current = null;
      }

      if (!result || !result.routes || result.routes.length === 0) return;

      const bounds: L.LatLngTuple[] = [];

      result.routes.forEach((route: Route, idx: number) => {
        if (!route || !route.geometry) return;

        const isSelected = selectedRoute === null || selectedRoute === idx;
        const color  = ROUTE_COLORS[idx] ?? '#3b82f6';
        const weight = selectedRoute === idx ? 5 : 3;
        const opacity = isSelected ? 1 : 0.3;

        // Polyline
        const latlngs: L.LatLngTuple[] = route.geometry.map(
          ([lon, lat]) => [lat, lon]
        );
        L.polyline(latlngs, { color, weight, opacity, lineJoin: 'round' }).addTo(layer);

        latlngs.forEach(ll => bounds.push(ll));

        // Checkpoints
        if (isSelected && route.checkpoints) {
          route.checkpoints.forEach((cp: Checkpoint) => {
            if (cp && cp.lat != null && cp.lon != null) {
              const marker = L.circleMarker([cp.lat, cp.lon], riskCircleStyle(cp.risk_level));
              marker.bindPopup(buildPopupHtml(cp, forecastHour), {
                maxWidth: 280,
                className: 'custom-popup',
              });
              marker.addTo(layer);
            }
          });
        }
      });

      // Origin / Destination markers
      if (result.origin_coords && result.origin_coords.length === 2) {
        const [oLon, oLat] = result.origin_coords;
        L.marker([oLat, oLon]).bindPopup('<b>📍 Origin</b>').addTo(layer);
      }
      if (result.dest_coords && result.dest_coords.length === 2) {
        const [dLon, dLat] = result.dest_coords;
        L.marker([dLat, dLon]).bindPopup('<b>🏁 Destination</b>').addTo(layer);
      }

      // Heat map layer (all checkpoints of currently selected route)
      const activeRoutes = selectedRoute !== null && result.routes[selectedRoute]
        ? [result.routes[selectedRoute]]
        : result.routes;

      const heatPoints: [number, number, number][] = [];
      activeRoutes.forEach(route => {
        if (route && route.checkpoints) {
          route.checkpoints.forEach(cp => {
            if (cp && cp.lat != null && cp.lon != null) {
              // Direct risk intensity: 0 -> 0.25 (green), 1 -> 0.45 (yellow), 2 -> 0.65 (orange), 3 -> 0.85 (red), 4 -> 1.0 (purple)
              const intensity = Math.min(1.0, 0.25 + ((cp.risk_level || 0) * 0.19));
              heatPoints.push([cp.lat, cp.lon, intensity]);
            }
          });
        }
      });

      if (heatPoints.length > 0 && typeof (L as any).heatLayer === 'function') {
        try {
          const heat = (L as any).heatLayer(heatPoints, {
            radius: 38,
            blur: 24,
            maxZoom: 12,
            gradient: {
              0.0: '#22c55e',
              0.35: '#eab308',
              0.60: '#f97316',
              0.80: '#ef4444',
              1.0: '#7c3aed'
            },
            minOpacity: 0.35,
          });
          heat.addTo(map);
          heatRef.current = heat;
        } catch (err) {
          console.warn('Leaflet heat layer creation skipped:', err);
        }
      }

      // Only auto-zoom once per new route result, not on every slider tick
      const resultKey = `${result.origin_coords?.join(',')}_${result.dest_coords?.join(',')}`;
      if (bounds.length > 0 && lastFitIdRef.current !== resultKey) {
        map.fitBounds(bounds, { padding: [40, 40] });
        lastFitIdRef.current = resultKey;
      }
    } catch (e) {
      console.error('Error rendering routes on map:', e);
    }
  }, [result, selectedRoute, forecastHour]);

  return (
    <>
      <div ref={divRef} style={{ width: '100%', height: '100%' }} />

      {/* Map legend */}
      {result && result.routes && (
        <div className="map-overlay">
          <div className="map-legend">
            <h4>Risk Level</h4>
            {RISK_LABELS.map((label, i) => (
              <div className="legend-item" key={i}>
                <div className="legend-dot" style={{ background: RISK_COLORS[i] }} />
                {label}
              </div>
            ))}
          </div>

          <div className="map-legend">
            <h4>Routes</h4>
            {result.routes.map((_, i) => (
              <div className="legend-item" key={i}>
                <div className="legend-dot" style={{ background: ROUTE_COLORS[i] ?? '#3b82f6', borderRadius: '2px' }} />
                Route {String.fromCharCode(65 + i)}{result.routes[i]?.recommended ? ' ✓' : ''}
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
