import React from 'react';
import type { Route } from '../api';

interface Props {
  routes: Route[];
  selectedIndex: number | null;
  onSelect: (index: number) => void;
}

const ROUTE_NAMES = ['Route A', 'Route B', 'Route C'];
const RISK_COLORS = ['#22c55e', '#eab308', '#f97316', '#ef4444', '#7c3aed'];

function RiskBar({ score }: { score: Route['score'] }) {
  if (!score) return null;
  const low = score.low_count || 0;
  const mod = score.moderate_count || 0;
  const high = score.high_count || 0;
  const severe = score.severe_count || 0;
  const notravel = score.no_travel_count || 0;
  const total = low + mod + high + severe + notravel;
  if (total === 0) return null;

  const segments = [
    { count: low,       color: '#22c55e' },
    { count: mod,       color: '#eab308' },
    { count: high,      color: '#f97316' },
    { count: severe,    color: '#ef4444' },
    { count: notravel,  color: '#7c3aed' },
  ];

  return (
    <div className="risk-bar">
      {segments.map((s, i) =>
        s.count > 0 ? (
          <div
            key={i}
            className="risk-bar-segment"
            style={{
              flex: s.count,
              background: s.color,
              opacity: 0.85,
            }}
            title={`${s.count} checkpoints`}
          />
        ) : null
      )}
    </div>
  );
}

export default function RouteList({ routes, selectedIndex, onSelect }: Props) {
  if (!routes || routes.length === 0) return null;

  return (
    <div className="routes-section">
      <h3>Route Options ({routes.length})</h3>
      {routes.map((route, i) => {
        if (!route) return null;
        const isSelected = selectedIndex === i;
        const avgRisk = route.score?.avg_risk ?? 0;
        const safeRiskIndex = Math.max(0, Math.min(4, Math.round(avgRisk)));
        const cardColor = route.recommended ? '#22c55e' : (RISK_COLORS[safeRiskIndex] ?? '#22c55e');

        return (
          <div
            key={i}
            className={`route-card ${isSelected ? 'selected' : ''} ${route.recommended ? 'recommended' : ''}`}
            style={{ '--card-accent': cardColor } as React.CSSProperties}
            onClick={() => onSelect(i)}
          >
            <div className="route-card-header">
              <div className="route-card-title">
                <span className="route-label">{ROUTE_NAMES[i] ?? `Route ${i + 1}`}</span>
                {route.recommended && (
                  <span className="badge-recommended">✓ Recommended</span>
                )}
              </div>
              {route.score?.no_travel && (
                <span className="risk-badge notravel">⛔ No Travel</span>
              )}
            </div>

            <div className="route-stats">
              <div className="stat-item">
                <div className="stat-label">Distance</div>
                <div className="stat-value">{(route.distance_miles ?? 0).toFixed(0)} mi</div>
              </div>
              <div className="stat-item">
                <div className="stat-label">Duration</div>
                <div className="stat-value">{(route.duration_hours ?? 0).toFixed(1)} hr</div>
              </div>
              <div className="stat-item">
                <div className="stat-label">Avg Risk</div>
                <div className="stat-value" style={{ color: cardColor }}>
                  {avgRisk.toFixed(2)}
                </div>
              </div>
              <div className="stat-item">
                <div className="stat-label">Checkpoints</div>
                <div className="stat-value">{route.checkpoints?.length ?? 0}</div>
              </div>
            </div>

            <div className="risk-counts">
              {(route.score?.severe_count ?? 0) > 0 && (
                <span className="risk-badge severe">🔴 {route.score?.severe_miles ?? (route.score!.severe_count * 25)} mi Severe</span>
              )}
              {(route.score?.high_count ?? 0) > 0 && (
                <span className="risk-badge high">🔶 {route.score?.high_miles ?? (route.score!.high_count * 25)} mi High</span>
              )}
              {(route.score?.moderate_count ?? 0) > 0 && (
                <span className="risk-badge mod">⚠️ {route.score?.moderate_count} Mod</span>
              )}
              {(route.score?.low_count ?? 0) > 0 && (
                <span className="risk-badge low">✅ {route.score?.low_count} Low</span>
              )}
              {(route.score?.no_travel_count ?? 0) > 0 && (
                <span className="risk-badge notravel">⛔ {route.score?.no_travel_miles ?? (route.score!.no_travel_count * 25)} mi No Travel</span>
              )}
            </div>

            {route.score && <RiskBar score={route.score} />}
          </div>
        );
      })}
    </div>
  );
}
