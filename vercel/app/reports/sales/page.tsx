import Link from 'next/link';
import { apiGet } from '../../../lib/api';

type Row = {
  id: number;
  fecha_venta: string;
  cliente: string;
  estado: string;
  total_venta: number | string;
};

function fmt(d: string | Date) {
  try { return new Date(d).toLocaleString(); } catch { return String(d); }
}

export default async function SalesReportPage({ searchParams }: { searchParams?: Record<string, string> }) {
  const sp = searchParams || {};
  const from = sp.from_date || new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10);
  const to = sp.to_date || new Date().toISOString().slice(0, 10);
  const qs = new URLSearchParams({ from_date: from, to_date: to });
  if (sp.customer_id) qs.set('customer_id', sp.customer_id);
  if (sp.product_id) qs.set('product_id', sp.product_id);
  if (sp.estado) qs.set('estado', sp.estado);

  let items: Row[] = [];
  let error: string | null = null;
  try {
    items = await apiGet<Row[]>(`/reports/sales?${qs.toString()}`);
  } catch (e: any) {
    error = e?.message || 'Error cargando reporte';
  }
  const total = items.reduce((acc, r) => acc + (typeof r.total_venta === 'string' ? parseFloat(r.total_venta) : (r.total_venta || 0)), 0);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
  const csvUrl = `${apiBase}/reports/sales.csv?${qs.toString()}`;
  const pdfUrl = `${apiBase}/reports/sales.pdf?${qs.toString()}`;

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Reporte de Ventas</h1>
      <form method="get" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <label>
          Desde
          <input type="date" name="from_date" defaultValue={from} />
        </label>
        <label>
          Hasta
          <input type="date" name="to_date" defaultValue={to} />
        </label>
        <input name="customer_id" placeholder="ID Cliente" defaultValue={sp.customer_id || ''} />
        <input name="product_id" placeholder="ID Producto" defaultValue={sp.product_id || ''} />
        <select name="estado" defaultValue={sp.estado || ''}>
          <option value="">(todos)</option>
          <option value="Confirmada">Confirmada</option>
          <option value="Pagada">Pagada</option>
          <option value="Reservada">Reservada</option>
          <option value="Cancelada">Cancelada</option>
          <option value="Eliminada">Eliminada</option>
        </select>
        <button type="submit">Filtrar</button>
        <a href={csvUrl} target="_blank" rel="noreferrer">Exportar CSV</a>
        <a href={pdfUrl} target="_blank" rel="noreferrer">Exportar PDF</a>
      </form>
      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}
      <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>ID</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Fecha</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Cliente</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Estado</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Total</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id}>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.id}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{fmt(r.fecha_venta)}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.cliente}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.estado}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{r.total_venta}</td>
            </tr>
          ))}
          {!items.length && !error && (
            <tr>
              <td colSpan={5} style={{ padding: 16, color: '#666' }}>Sin resultados</td>
            </tr>
          )}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={4} style={{ padding: 8, textAlign: 'right', fontWeight: 700 }}>Total</td>
            <td style={{ padding: 8, textAlign: 'right', fontWeight: 700 }}>{total.toFixed(2)}</td>
          </tr>
        </tfoot>
      </table>
      </div>
      <p style={{ marginTop: 24 }}>
        <Link href="/">Volver</Link>
      </p>
    </div>
  );
}
