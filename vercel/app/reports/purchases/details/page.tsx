import Link from 'next/link';
import { apiGet } from '../../../../lib/api';

type Row = { id_compra: number; fecha_compra: string; proveedor: string; id_producto: number; sku: string; producto: string; cantidad: number; precio_unitario: number | string; subtotal: number | string };

export default async function PurchasesDetailsReportPage({ searchParams }: { searchParams?: Record<string, string> }) {
  const sp = searchParams || {};
  const from = sp.from_date || new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10);
  const to = sp.to_date || new Date().toISOString().slice(0, 10);
  const qs = new URLSearchParams({ from_date: from, to_date: to });
  if (sp.supplier_id) qs.set('supplier_id', sp.supplier_id);
  if (sp.estado) qs.set('estado', sp.estado);

  let items: Row[] = [];
  let error: string | null = null;
  try { items = await apiGet<Row[]>(`/reports/purchases/details?${qs.toString()}`); } catch (e: any) { error = e?.message || 'Error'; }

  const total = items.reduce((acc, r) => acc + (typeof r.subtotal === 'string' ? parseFloat(r.subtotal) : (r.subtotal || 0)), 0);
  return (
    <div>
      <h1>Detalle de Compras</h1>
      <form method="get" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <label>Desde <input type="date" name="from_date" defaultValue={from} /></label>
        <label>Hasta <input type="date" name="to_date" defaultValue={to} /></label>
        <input name="supplier_id" placeholder="ID Proveedor" defaultValue={sp.supplier_id || ''} />
        <select name="estado" defaultValue={sp.estado || ''}>
          <option value="">(todos)</option>
          <option>Pendiente</option>
          <option>Incompleta</option>
          <option>Por pagar</option>
          <option>Completada</option>
          <option>Cancelada</option>
          <option>Eliminada</option>
        </select>
        <button type="submit">Filtrar</button>
      </form>
      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}
      <div className="table-wrap">
      <table>
        <thead><tr><th>OC</th><th>Fecha</th><th>Proveedor</th><th>ID Prod</th><th>SKU</th><th>Producto</th><th style={{ textAlign: 'right' }}>Cant.</th><th style={{ textAlign: 'right' }}>P. Unit.</th><th style={{ textAlign: 'right' }}>Subtotal</th></tr></thead>
        <tbody>
          {items.map((r, i) => (
            <tr key={i}>
              <td>{r.id_compra}</td>
              <td>{new Date(r.fecha_compra).toLocaleString()}</td>
              <td>{r.proveedor}</td>
              <td>{r.id_producto}</td>
              <td>{r.sku}</td>
              <td>{r.producto}</td>
              <td style={{ textAlign: 'right' }}>{r.cantidad}</td>
              <td style={{ textAlign: 'right' }}>{r.precio_unitario}</td>
              <td style={{ textAlign: 'right' }}>{r.subtotal}</td>
            </tr>
          ))}
          {!items.length && !error && (<tr><td colSpan={9} style={{ padding: 16 }} className="muted">Sin resultados</td></tr>)}
        </tbody>
        <tfoot><tr><td colSpan={8} style={{ textAlign: 'right', fontWeight: 700 }}>Total</td><td style={{ textAlign: 'right', fontWeight: 700 }}>{total.toFixed(2)}</td></tr></tfoot>
      </table>
      </div>
      <p style={{ marginTop: 16 }}><Link href="/reports">Volver</Link></p>
    </div>
  );
}
