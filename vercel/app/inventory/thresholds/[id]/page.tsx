"use client";
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';

export default function ThresholdEditPage() {
  const { id } = useParams() as { id: string };
  const r = useRouter();
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
  const [form, setForm] = useState<{ min_value: string; max_value: string }>({ min_value: '0', max_value: '0' });
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${apiBase}/inventory/thresholds/${id}`, { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setForm({ min_value: String(data.min_value ?? 0), max_value: String(data.max_value ?? 0) });
      } catch (e: any) {
        setErr(e?.message || 'Error');
      }
    })();
  }, [id]);

  const onChange = (e: any) => setForm({ ...form, [e.target.name]: e.target.value });
  const onSubmit = async (e: any) => {
    e.preventDefault(); setErr(null); setLoading(true);
    try {
      const res = await fetch(`${apiBase}/inventory/thresholds/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ min_value: parseInt(form.min_value || '0'), max_value: parseInt(form.max_value || '0') }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      r.push('/inventory');
    } catch (e: any) {
      setErr(e?.message || 'Error');
    } finally { setLoading(false); }
  };

  return (
    <div>
      <h1>Umbral de Inventario (Producto #{id})</h1>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 8, maxWidth: 360 }}>
        <label>
          Mínimo
          <input name="min_value" value={form.min_value} onChange={onChange} />
        </label>
        <label>
          Máximo
          <input name="max_value" value={form.max_value} onChange={onChange} />
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <button disabled={loading} type="submit">Guardar</button>
          <Link href="/inventory">Cancelar</Link>
        </div>
      </form>
    </div>
  );
}

