"use client";
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiDelete, apiGet, apiPut } from '../../../../lib/api';

type Customer = {
  id: number; razon_social: string; rut: string; contacto?: string; telefono?: string; email?: string; direccion?: string;
};

export default function EditCustomerPage() {
  const { id } = useParams() as { id: string };
  const r = useRouter();
  const [form, setForm] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try { const s = await apiGet<Customer>(`/customers/${id}`); setForm({ ...s }); }
      catch (e: any) { setErr(e?.message || 'Error'); }
    })();
  }, [id]);

  const onChange = (e: any) => setForm({ ...form, [e.target.name]: e.target.value });
  const onSubmit = async (e: any) => {
    e.preventDefault(); setErr(null); setLoading(true);
    try { await apiPut(`/customers/${id}`, form); r.push('/customers'); }
    catch (e: any) { setErr(e?.message || 'Error'); }
    finally { setLoading(false); }
  };
  const onDelete = async () => {
    if (!confirm('¿Eliminar cliente?')) return;
    try { await apiDelete(`/customers/${id}`); r.push('/customers'); }
    catch (e: any) { setErr(e?.message || 'Error'); }
  };

  if (!form) return <p>Cargando...</p>;
  return (
    <div>
      <h1>Editar Cliente #{id}</h1>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 8, maxWidth: 520 }}>
        <input required name="razon_social" placeholder="Razón social" value={form.razon_social} onChange={onChange} />
        <input required name="rut" placeholder="RUT" value={form.rut} onChange={onChange} />
        <input name="contacto" placeholder="Contacto" value={form.contacto || ''} onChange={onChange} />
        <input name="telefono" placeholder="Teléfono" value={form.telefono || ''} onChange={onChange} />
        <input name="email" placeholder="Email" value={form.email || ''} onChange={onChange} />
        <input name="direccion" placeholder="Dirección" value={form.direccion || ''} onChange={onChange} />
        <div style={{ display: 'flex', gap: 8 }}>
          <button disabled={loading} type="submit">Guardar</button>
          <button type="button" onClick={onDelete} style={{ color: 'crimson' }}>Eliminar</button>
          <Link href="/customers">Cancelar</Link>
        </div>
      </form>
    </div>
  );
}
