"use client";
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiPost } from '../../../lib/api';

export default function NewSupplierPage() {
  const r = useRouter();
  const [form, setForm] = useState({ razon_social: '', rut: '', contacto: '', telefono: '', email: '', direccion: '' });
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const onChange = (e: any) => setForm({ ...form, [e.target.name]: e.target.value });
  const onSubmit = async (e: any) => {
    e.preventDefault(); setErr(null); setLoading(true);
    try { await apiPost('/suppliers', form); r.push('/suppliers'); }
    catch (e: any) { setErr(e?.message || 'Error'); }
    finally { setLoading(false); }
  };
  return (
    <div>
      <h1>Nuevo Proveedor</h1>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 8, maxWidth: 520 }}>
        <input required name="razon_social" placeholder="Razón social" value={form.razon_social} onChange={onChange} />
        <input required name="rut" placeholder="RUT" value={form.rut} onChange={onChange} />
        <input name="contacto" placeholder="Contacto" value={form.contacto} onChange={onChange} />
        <input name="telefono" placeholder="Teléfono" value={form.telefono} onChange={onChange} />
        <input name="email" placeholder="Email" value={form.email} onChange={onChange} />
        <input name="direccion" placeholder="Dirección" value={form.direccion} onChange={onChange} />
        <div style={{ display: 'flex', gap: 8 }}>
          <button disabled={loading} type="submit">Guardar</button>
          <Link href="/suppliers">Cancelar</Link>
        </div>
      </form>
    </div>
  );
}

