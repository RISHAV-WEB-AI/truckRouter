import { useState, useRef, useMemo } from 'react';
import './index.css';
import { submitRoute, pollJob } from './api';
import type { JobResult, RouteRequest } from './api';
import RouteForm from './components/RouteForm';
import RouteList from './components/RouteList';
import MapView from './components/MapView';
import { computeForecastRoutes } from './forecastUtils';

const POLL_INTERVAL_MS = 2500;
const MAX_POLLS = 60; // 2.5s × 60 = 2.5 minutes timeout

export default function App() {
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState<string | null>(null);
  const [result, setResult]             = useState<JobResult | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<number | null>(null);
  const [forecastHour, setForecastHour] = useState(0);
  const [loadWeight, setLoadWeight]     = useState<number>(35000);
  const [jobStatus, setJobStatus]       = useState<string>('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const handleSubmit = async (data: RouteRequest) => {
    setLoading(true);
    setError(null);
    setResult(null);
    setSelectedRoute(null);
    setForecastHour(0);
    setLoadWeight(data.load_weight_lbs || 35000);
    setJobStatus('Submitting request…');
    stopPolling();

    try {
      const { job_id } = await submitRoute(data);
      setJobStatus('Processing routes & weather data…');

      let polls = 0;
      let consecutiveErrors = 0;
      pollRef.current = setInterval(async () => {
        polls++;
        try {
          const job = await pollJob(job_id);
          consecutiveErrors = 0; // reset on successful ping
          setJobStatus(`Status: ${job.status}`);

          if (job.status === 'done' && job.result) {
            stopPolling();
            const res = job.result as JobResult;
            setResult(res);
            setSelectedRoute(res.recommended_index ?? 0);
            setLoading(false);
            setJobStatus('');
          } else if (job.status === 'error') {
            stopPolling();
            const errResult = job.result as { error: string } | null;
            setError(errResult?.error ?? 'Route computation failed.');
            setLoading(false);
            setJobStatus('');
          } else if (polls >= MAX_POLLS) {
            stopPolling();
            setError('Request timed out. Please try again.');
            setLoading(false);
            setJobStatus('');
          }
        } catch (e: any) {
          consecutiveErrors++;
          console.warn(`Poll error (${consecutiveErrors}/4):`, e);
          if (consecutiveErrors >= 4) {
            stopPolling();
            setError(e.message ?? 'Network error while polling.');
            setLoading(false);
            setJobStatus('');
          }
        }
      }, POLL_INTERVAL_MS);
    } catch (e: any) {
      setError(e.response?.data?.detail ?? e.message ?? 'Failed to submit request.');
      setLoading(false);
      setJobStatus('');
    }
  };

  // Re-calculate forecast weather, risk rules, and recommended route for the selected forecast hour
  const { displayRoutes, currentRecommendedIndex } = useMemo(() => {
    if (!result?.routes) return { displayRoutes: [], currentRecommendedIndex: 0 };
    const { routes, recommendedIndex } = computeForecastRoutes(result.routes, forecastHour, loadWeight);
    return { displayRoutes: routes, currentRecommendedIndex: recommendedIndex };
  }, [result, forecastHour, loadWeight]);

  const displayResult: JobResult | null = useMemo(() => {
    if (!result) return null;
    return {
      ...result,
      routes: displayRoutes,
      recommended_index: currentRecommendedIndex,
    };
  }, [result, displayRoutes, currentRecommendedIndex]);

  const sliderMax = 48;
  const sliderProgress = (forecastHour / sliderMax) * 100;

  // Derive corridor weather summary at this forecast hour
  const activeRoute = displayRoutes[selectedRoute ?? 0] || displayRoutes[0];
  const maxWindAtHour = activeRoute?.checkpoints
    ? Math.max(...activeRoute.checkpoints.map(c => c.weather?.wind_mph || 0))
    : 0;
  const maxRainAtHour = activeRoute?.checkpoints
    ? Math.max(...activeRoute.checkpoints.map(c => ((c.weather?.rain_mm || 0) / 25.4)))
    : 0;

  return (
    <div className="app-layout">
      {/* ── Sidebar ─────────────────────────────────── */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <span className="logo-icon">🚛</span>
          <h1>TruckRouter</h1>
          <p>Weather-aware safe routing for heavy loads</p>
        </div>

        <div className="sidebar-content">
          {/* Input form */}
          <RouteForm onSubmit={handleSubmit} loading={loading} />

          {/* Loading banner */}
          {loading && (
            <div className="loading-banner">
              <div className="spinner" />
              <span>{jobStatus}</span>
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div className="error-banner">⚠️ {error}</div>
          )}

          {/* Forecast slider with live condition readout */}
          {result && (
            <div className="slider-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <h3 style={{ margin: 0 }}>🌦 0–48h Forecast Slider</h3>
                <span className="slider-time" style={{ fontSize: '0.85rem' }}>+{forecastHour}h</span>
              </div>
              
              <div className="slider-row">
                <input
                  type="range"
                  id="forecast-slider"
                  min={0}
                  max={sliderMax}
                  step={1}
                  value={forecastHour}
                  style={{ '--progress': `${sliderProgress}%` } as React.CSSProperties}
                  onChange={e => setForecastHour(Number(e.target.value))}
                />
              </div>

              {/* Live readout of corridor condition changes */}
              <div style={{
                marginTop: '10px',
                padding: '8px 10px',
                background: 'rgba(255,255,255,0.04)',
                borderRadius: '6px',
                fontSize: '0.73rem',
                display: 'flex',
                justifyContent: 'space-between',
                color: '#94a3b8'
              }}>
                <span>💨 Peak Wind: <b style={{ color: maxWindAtHour >= 45 ? '#ef4444' : maxWindAtHour >= 35 ? '#f97316' : '#22c55e' }}>{maxWindAtHour} mph</b></span>
                <span>🌧 Peak Rain: <b style={{ color: maxRainAtHour >= 0.5 ? '#ef4444' : maxRainAtHour >= 0.25 ? '#f97316' : '#22c55e' }}>{maxRainAtHour.toFixed(2)} in/h</b></span>
              </div>
            </div>
          )}

          {/* Route cards reacting dynamically to the slider */}
          {result && (
            <RouteList
              routes={displayRoutes}
              selectedIndex={selectedRoute}
              onSelect={idx => setSelectedRoute(idx)}
            />
          )}
        </div>
      </aside>

      {/* ── Map reacting dynamically to the slider ───────────────── */}
      <main className="map-container">
        <MapView
          result={displayResult}
          selectedRoute={selectedRoute}
          forecastHour={forecastHour}
        />
      </main>
    </div>
  );
}
