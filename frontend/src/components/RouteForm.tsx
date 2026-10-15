import React, { useState } from 'react';
import type { RouteRequest } from '../api';

interface Props {
  onSubmit: (data: RouteRequest) => void;
  loading: boolean;
}

const PRESETS = [
  { label: 'Chicago ➔ Dallas (968 mi)', origin: 'Chicago, IL', destination: 'Dallas, TX', weight: 42000 },
  { label: 'New York ➔ Atlanta (870 mi)', origin: 'New York, NY', destination: 'Atlanta, GA', weight: 35000 },
  { label: 'Denver ➔ Phoenix (820 mi)', origin: 'Denver, CO', destination: 'Phoenix, AZ', weight: 48000 },
];

function getNowLocalIso(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

export default function RouteForm({ onSubmit, loading }: Props) {
  const [form, setForm] = useState<RouteRequest>({
    origin: 'Chicago, IL',
    destination: 'Dallas, TX',
    departure_time: getNowLocalIso(),
    load_weight_lbs: 42000,
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: type === 'number' ? parseFloat(value) || 0 : value,
    }));
  };

  const handleApplyPreset = (preset: typeof PRESETS[0]) => {
    setForm({
      origin: preset.origin,
      destination: preset.destination,
      departure_time: getNowLocalIso(),
      load_weight_lbs: preset.weight,
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.origin || !form.destination || !form.departure_time) return;
    onSubmit(form);
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="form-section">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <h3 style={{ margin: 0 }}>Route Details</h3>
          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>US Continental Truck Routes</span>
        </div>

        {/* Quick Route Preset Chips */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '14px' }}>
          {PRESETS.map((p, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleApplyPreset(p)}
              style={{
                fontSize: '0.72rem',
                background: '#1e293b',
                color: '#38bdf8',
                border: '1px solid #334155',
                borderRadius: '6px',
                padding: '4px 8px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = '#38bdf8')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = '#334155')}
            >
              ⚡ {p.label}
            </button>
          ))}
        </div>

        <div className="form-group">
          <label htmlFor="origin">📍 Origin (City, State)</label>
          <input
            id="origin"
            name="origin"
            type="text"
            placeholder="e.g. Chicago, IL"
            value={form.origin}
            onChange={handleChange}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="destination">🏁 Destination (City, State)</label>
          <input
            id="destination"
            name="destination"
            type="text"
            placeholder="e.g. Dallas, TX"
            value={form.destination}
            onChange={handleChange}
            required
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="departure_time">🕐 Departure</label>
            <input
              id="departure_time"
              name="departure_time"
              type="datetime-local"
              value={form.departure_time}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="load_weight_lbs">⚖️ Load (lbs)</label>
            <input
              id="load_weight_lbs"
              name="load_weight_lbs"
              type="number"
              placeholder="e.g. 42000"
              min={0}
              max={80000}
              value={form.load_weight_lbs || ''}
              onChange={handleChange}
            />
          </div>
        </div>
      </div>

      <button type="submit" className="btn-submit" disabled={loading}>
        {loading ? '⏳ Calculating Routes…' : '🚛 Find Safest Route'}
      </button>
    </form>
  );
}
