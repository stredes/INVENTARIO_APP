"use client";
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiGet, apiPut } from '../../../../lib/api';

type Sale = {
  id: number;
  estado: string;
  fecha_venta?: string | null;
};

export default function EditSalePage() {
  const { id } = useParams() as { id: string };
  const r = useRouter();
  const [form, setForm] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const s = await apiGet<Sale>(`/sales/${id}`);
        setForm({ estado: s.estado || '', fecha_venta: s.fecha_venta ? String(s.fecha_venta) : '' });
      } catch (e: any) { setErr(e?.message || 'Error'); }
    })();
  }, [id]);

  const onChange = (e: any) => setForm({ ...form, [e.target.name]: e.target.value });
  const onSubmit = async (e: any) => {
    e.preventDefault(); setErr(null); setLoading(true);
    try {
      const payload: any = { estado: form.estado || null, fecha_venta: form.fecha_venta || null };
      await apiPut(`/sales/${id}`, payload);
      r.push('/sales');
    } catch (e: any) { setErr(e?.message || 'Error'); } finally { setLoading(false); }
  };

  if (!form) return <p>Cargando...</p>;
  return (
    <div>
      <h1>Editar Venta #{id}</h1>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 8, maxWidth: 480 }}>
        <label>Estado
          <select name="estado" value={form.estado} onChange={onChange}>
            <option value="">(sin cambio)</option>
            <option>Confirmada</option>
            <option>Pagada</option>
            <option>Reservada</option>
            <option>Cancelada</option>
            <option>Eliminada</option>
          </select>
        </label>
        <label>Fecha Venta
          <input type="datetime-local" name="fecha_venta" value={form.fecha_venta} onChange={onChange} />
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <button disabled={loading} type="submit">Guardar</button>
          <Link href="/sales">Cancelar</Link>
        </div>
      </form>
    </div>
  );
}

