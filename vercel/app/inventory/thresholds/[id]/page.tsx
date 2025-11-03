"use client";
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiGet, apiPost } from '../../../../lib/api';

type Threshold = { product_id: number; min_value: number; max_value: number };

export default function ThresholdEditorPage() {
  const { id } = useParams() as { id: string };
  const r = useRouter();
  const [data, setData] = useState<Threshold | null>(null);
  const [minV, setMinV] = useState('');
  const [maxV, setMaxV] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const t = await apiGet<Threshold>(`/inventory/thresholds/${id}`);
        setData(t);
        setMinV(String(t.min_value ?? 0));
        setMaxV(String(t.max_value ?? 0));
      } catch (e: any) { setErr(e?.message || 'Error cargando umbrales'); }
    })();
  }, [id]);

  const onSubmit = async (e: any) => {
    e.preventDefault(); setErr(null); setLoading(true);
    try {
      const payload = { min_value: parseInt(minV || '0'), max_value: parseInt(maxV || '0') };
      if (payload.min_value < 0 || payload.max_value < 0) throw new Error('Valores no pueden ser negativos');
      if (payload.max_value && payload.min_value && payload.max_value < payload.min_value) throw new Error('Max debe ser >= Min');
      await apiPost(`/inventory/thresholds/${id}`, payload);
      r.push('/inventory');
    } catch (e: any) { setErr(e?.message || 'Error al guardar'); }
    finally { setLoading(false); }
  };

  if (!data) return <p>Cargando...</p>;
  return (
    <div>
      <h1>Umbrales de Inventario – Prod #{id}</h1>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}
      <form onSubmit={onSubmit} className="grid-3" style={{ maxWidth: 520, alignItems: 'end' }}>
        <label>
          Mínimo
          <input type="number" value={minV} onChange={(e) => setMinV(e.target.value)} />
        </label>
        <label>
          Máximo
          <input type="number" value={maxV} onChange={(e) => setMaxV(e.target.value)} />
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" disabled={loading} type="submit">Guardar</button>
          <Link className="btn" href="/inventory">Cancelar</Link>
        </div>
      </form>
    </div>
  );
}

