import Link from 'next/link';
import { apiGet } from '../../lib/api';
import Accordion from '../../components/Accordion';

type Sale = {
  id: number;
  id_cliente: number;
  fecha_venta: string;
  total_venta: number | string;
  estado: string;
};

export default async function SalesPage({ searchParams }: { searchParams?: Record<string, string> }) {
  const sp = searchParams || {};
  const from = sp.from_date || new Date(new Date().getFullYear(),0,1).toISOString().slice(0,10);
  const to = sp.to_date || new Date().toISOString().slice(0,10);
  const qs = new URLSearchParams({ from_date: from, to_date: to });
  if (sp.customer_id) qs.set('customer_id', sp.customer_id);
  if (sp.estado) qs.set('estado', sp.estado);
  let items: Sale[] = [];
  let error: string | null = null;
  try { items = await apiGet<Sale[]>(`/sales?${qs.toString()}`); }
  catch (e: any) { error = e?.message || 'Error cargando ventas'; }
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Ventas</h1>
      <div className="accordion" style={{ marginBottom: 12 }}>
        <Accordion title="Acciones rápidas" defaultOpen>
          <div className="grid-3">
            <Link className="btn" href="/sales/new">+ Nueva venta</Link>
            <Link className="btn" href="/quotes/new">Nueva cotización</Link>
          </div>
        </Accordion>
      </div>
      <div className="accordion" style={{ marginBottom: 12 }}>
        <Accordion title="Filtros" defaultOpen>
          <form method="get" className="grid-4" style={{ alignItems: 'end' }}>
            <label>Desde<input type="date" name="from_date" defaultValue={from} /></label>
            <label>Hasta<input type="date" name="to_date" defaultValue={to} /></label>
            <label>Cliente ID<input name="customer_id" defaultValue={sp.customer_id || ''} /></label>
            <label>Estado
              <select name="estado" defaultValue={sp.estado || ''}>
                <option value="">(todos)</option>
                <option>Confirmada</option>
                <option>Pagada</option>
                <option>Reservada</option>
                <option>Cancelada</option>
                <option>Eliminada</option>
              </select>
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" type="submit">Aplicar</button>
              <a className="btn" href="/sales">Limpiar</a>
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
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Cliente</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Fecha</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Total</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Estado</th>
            <th style={{ textAlign: 'center', borderBottom: '1px solid #ddd', padding: 8 }}>PDF</th>
            <th style={{ textAlign: 'center', borderBottom: '1px solid #ddd', padding: 8 }}>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.id}>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.id}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.id_cliente}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{new Date(s.fecha_venta).toLocaleString()}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{s.total_venta}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.estado}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'center' }}>
                <a href={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/sales/${s.id}/pdf`} target="_blank">Ver</a>
              </td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'center' }}>
                <a href={`/sales/${s.id}/edit`}>Editar</a>
              </td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'center' }}>
                <form action={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000'}/sales/${s.id}/cancel?revert_stock=true`} method="post" style={{ display: 'inline' }}>
                  <button type="submit">Cancelar</button>
                </form>
              </td>
            </tr>
          ))}
          {!items.length && !error && (
            <tr>
              <td colSpan={6} style={{ padding: 16, color: '#666' }}>No hay ventas</td>
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
