"use client";
import React from 'react';
import { apiPost } from '../../lib/api';

export default function CustomerQuickForm() {
  const [form, setForm] = React.useState({ razon_social: '', rut: '', contacto: '', telefono: '', email: '', direccion: '' });
  const [err, setErr] = React.useState<string | null>(null);
  const [ok, setOk] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const onChange = (e: any) => setForm({ ...form, [e.target.name]: e.target.value });
  const onSubmit = async (e: any) => {
    e.preventDefault(); setErr(null); setOk(null); setLoading(true);
    try { await apiPost('/customers', form); setOk('Cliente creado'); setForm({ razon_social: '', rut: '', contacto: '', telefono: '', email: '', direccion: '' }); }
    catch (e: any) { setErr(e?.message || 'Error'); } finally { setLoading(false); }
  };
  return (
    <form onSubmit={onSubmit} className="grid-3" style={{ alignItems: 'end' }}>
      <label>Razón social<input name="razon_social" value={form.razon_social} onChange={onChange} required /></label>
      <label>RUT<input name="rut" value={form.rut} onChange={onChange} required /></label>
      <label>Contacto<input name="contacto" value={form.contacto} onChange={onChange} /></label>
      <label>Teléfono<input name="telefono" value={form.telefono} onChange={onChange} /></label>
      <label>Email<input name="email" value={form.email} onChange={onChange} /></label>
      <label>Dirección<input name="direccion" value={form.direccion} onChange={onChange} /></label>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn btn-primary" disabled={loading} type="submit">Agregar</button>
        {ok && <span className="muted">{ok}</span>}
        {err && <span style={{ color: 'crimson' }}>{err}</span>}
      </div>
    </form>
  );
}

