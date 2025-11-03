"use client";
import React from 'react';

export default function LocationQuickForm() {
  const [form, setForm] = React.useState({ nombre: '', descripcion: '' });
  const [err, setErr] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
  const onChange = (e: any) => setForm({ ...form, [e.target.name]: e.target.value });
  const onSubmit = async (e: any) => {
    e.preventDefault(); setErr(null); setLoading(true);
    try {
      const res = await fetch(`${apiBase}/locations`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre: form.nombre, descripcion: form.descripcion || null }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      window.location.href = '/locations';
    } catch (e: any) { setErr(e?.message || 'Error'); } finally { setLoading(false); }
  };
  return (
    <form onSubmit={onSubmit} className="grid-3" style={{ alignItems: 'end' }}>
      <label>Nombre<input name="nombre" value={form.nombre} onChange={onChange} required /></label>
      <label>Descripción<input name="descripcion" value={form.descripcion} onChange={onChange} /></label>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn btn-primary" disabled={loading} type="submit">Crear</button>
        {err && <span style={{ color: 'crimson' }}>{err}</span>}
      </div>
    </form>
  );
}

