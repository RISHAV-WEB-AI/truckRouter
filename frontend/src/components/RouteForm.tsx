import React, { useState } from 'react';
import type { RouteRequest } from '../api';

interface Props {
  onSubmit: (data: RouteRequest) => void;
  loading: boolean;
}

export default function RouteForm({ onSubmit, loading }: Props) {
  const [form, setForm] = useState<RouteRequest>({
    origin: '',
    destination: '',
    departure_time: '',
    load_weight_lbs: 0,
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: type === 'number' ? parseFloat(value) || 0 : value,
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.origin || !form.destination || !form.departure_time) return;
    onSubmit(form);
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="form-section">
        <h3>Route Details</h3>

        <div className="form-group">
          <label htmlFor="origin">📍 Origin</label>
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
          <label htmlFor="destination">🏁 Destination</label>
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
              placeholder="e.g. 35000"
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
