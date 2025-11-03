import Link from 'next/link';
import { apiGet } from '../../lib/api';
import Accordion from '../../components/Accordion';

type Purchase = {
  id: number;
  id_proveedor: number;
  fecha_compra: string;
  total_compra: number | string;
  estado: string;
};

export default async function PurchasesPage({ searchParams }: { searchParams?: Record<string, string> }) {
  const sp = searchParams || {};
  const qs = new URLSearchParams();
  const from = sp.from_date || new Date(new Date().getFullYear(),0,1).toISOString().slice(0,10);
  const to = sp.to_date || new Date().toISOString().slice(0,10);
  qs.set('from_date', from); qs.set('to_date', to);
  if (sp.supplier_id) qs.set('supplier_id', sp.supplier_id);
  if (sp.estado) qs.set('estado', sp.estado);
  let items: Purchase[] = [];
  let error: string | null = null;
  try { items = await apiGet<Purchase[]>(`/purchases?${qs.toString()}`); }
  catch (e: any) { error = e?.message || 'Error cargando compras'; }
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Compras</h1>
      <div className="accordion" style={{ marginBottom: 12 }}>
        <Accordion title="Acciones rápidas" defaultOpen>
          <div className="grid-3">
            <Link className="btn" href="/purchases/new">+ Nueva compra</Link>
            <Link className="btn" href="/receptions">Recepciones</Link>
            <Link className="btn" href="/orders">Órdenes (admin)</Link>
          </div>
        </Accordion>
      </div>
      <div className="accordion" style={{ marginBottom: 12 }}>
        <Accordion title="Filtros" defaultOpen>
          <form method="get" className="grid-4" style={{ alignItems: 'end' }}>
            <label>Desde<input type="date" name="from_date" defaultValue={from} /></label>
            <label>Hasta<input type="date" name="to_date" defaultValue={to} /></label>
            <label>Proveedor ID<input name="supplier_id" defaultValue={sp.supplier_id || ''} /></label>
            <label>Estado
              <select name="estado" defaultValue={sp.estado || ''}>
                <option value="">(todos)</option>
                <option>Pendiente</option>
                <option>Incompleta</option>
                <option>Por pagar</option>
                <option>Completada</option>
                <option>Cancelada</option>
                <option>Eliminada</option>
              </select>
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" type="submit">Aplicar</button>
              <a className="btn" href="/purchases">Limpiar</a>
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
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Proveedor</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Fecha</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Total</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Estado</th>
            <th style={{ textAlign: 'center', borderBottom: '1px solid #ddd', padding: 8 }}>PDF</th>
            <th style={{ textAlign: 'center', borderBottom: '1px solid #ddd', padding: 8 }}>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {items.map((p) => (
            <tr key={p.id}>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{p.id}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{p.id_proveedor}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{new Date(p.fecha_compra).toLocaleString()}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{p.total_compra}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{p.estado} <a href={`/purchases/${p.id}/receive`} style={{ marginLeft: 12 }}>Recepcionar</a> <a href={`/purchases/${p.id}/edit`} style={{ marginLeft: 12 }}>Editar</a></td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'center' }}>
                <a href={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/purchases/${p.id}/pdf`} target="_blank">Ver</a>
              </td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'center' }}>
                <form action={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000'}/purchases/${p.id}/cancel?revert_stock=true`} method="post" style={{ display: 'inline' }}>
                  <button type="submit">Cancelar</button>
                </form>
              </td>
            </tr>
          ))}
          {!items.length && !error && (
            <tr>
              <td colSpan={6} style={{ padding: 16, color: '#666' }}>No hay compras</td>
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
