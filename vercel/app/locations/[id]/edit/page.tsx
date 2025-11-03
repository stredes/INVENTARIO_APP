"use client";
import React from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiGet } from '../../../../lib/api';

type Location = { id: number; nombre: string; descripcion?: string | null };

export default function EditLocationPage() {
  const { id } = useParams() as { id: string };
  const r = useRouter();
  const [form, setForm] = React.useState<{ nombre: string; descripcion: string } | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

  React.useEffect(() => {
    (async () => {
      try {
        const all = await apiGet<Location[]>(`/locations`);
        const cur = all.find(x => String(x.id) === String(id));
        if (!cur) throw new Error('Ubicación no encontrada');
        setForm({ nombre: cur.nombre, descripcion: cur.descripcion || '' });
      } catch (e: any) { setErr(e?.message || 'Error'); }
    })();
  }, [id]);

  const onChange = (e: any) => form && setForm({ ...form, [e.target.name]: e.target.value });
  const onSubmit = async (e: any) => {
    e.preventDefault(); if (!form) return; setErr(null); setLoading(true);
    try {
      const res = await fetch(`${apiBase}/locations/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nombre: form.nombre, descripcion: form.descripcion || null }) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      r.push('/locations');
    } catch (e: any) { setErr(e?.message || 'Error'); } finally { setLoading(false); }
  };
  const onDelete = async () => {
    if (!confirm('¿Eliminar ubicación?')) return;
    try {
      const res = await fetch(`${apiBase}/locations/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      r.push('/locations');
    } catch (e: any) { setErr(e?.message || 'Error al eliminar'); }
  };

  if (!form) return <p>Cargando...</p>;
  return (
    <div>
      <h1>Editar Ubicación #{id}</h1>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 8, maxWidth: 480 }}>
        <input required name="nombre" value={form.nombre} onChange={onChange} placeholder="Nombre" />
        <input name="descripcion" value={form.descripcion} onChange={onChange} placeholder="Descripción" />
        <div style={{ display: 'flex', gap: 8 }}>
          <button disabled={loading} type="submit">Guardar</button>
          <button type="button" onClick={onDelete} style={{ color: 'crimson' }}>Eliminar</button>
          <Link href="/locations">Cancelar</Link>
        </div>
      </form>
    </div>
  );
}

