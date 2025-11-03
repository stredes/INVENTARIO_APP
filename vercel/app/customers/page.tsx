import Link from 'next/link';
import { apiGet } from '../../lib/api';
import Accordion from '../../components/Accordion';
import CustomerQuickForm from '../../components/forms/CustomerQuickForm';

type Customer = {
  id: number;
  razon_social: string;
  rut: string;
  contacto?: string;
  telefono?: string;
  email?: string;
};

export default async function CustomersPage({ searchParams }: { searchParams?: Record<string, string> }) {
  const sp = searchParams || {};
  const qs = new URLSearchParams(); if (sp.q) qs.set('q', sp.q);
  let items: Customer[] = [];
  let error: string | null = null;
  try { items = await apiGet<Customer[]>(`/customers?${qs.toString()}`); } catch (e: any) { error = e?.message || 'Error cargando clientes'; }
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Clientes</h1>
      <div className="accordion">
        <Accordion title="Cliente (rápido)" defaultOpen>
          <CustomerQuickForm />
        </Accordion>
      </div>
      <div className="accordion" style={{ marginTop: 12 }}>
        <Accordion title="Filtros">
          <form method="get" className="grid-3" style={{ alignItems: 'end' }}>
            <label>Búsqueda<input name="q" defaultValue={sp.q || ''} placeholder="Nombre o RUT" /></label>
            <div />
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" type="submit">Aplicar</button>
              <a className="btn" href="/customers">Limpiar</a>
            </div>
          </form>
        </Accordion>
      </div>
      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}
      <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>ID</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Razón Social</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>RUT</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Contacto</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Teléfono</th>
          </tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.id}>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.id}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.razon_social} <a href={`/customers/${s.id}/edit`} style={{ marginLeft: 12 }}>Editar</a></td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.rut}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.contacto || '-'}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.telefono || '-'}</td>
            </tr>
          ))}
          {!items.length && !error && (
            <tr>
              <td colSpan={5} style={{ padding: 16, color: '#666' }}>No hay clientes</td>
            </tr>
          )}
        </tbody>
      </table>
      </div>
      <p style={{ marginTop: 24 }}>
        <Link href="/">Volver</Link>
      </p>
    </div>
  );
}
