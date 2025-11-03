import Link from 'next/link';
import { apiGet } from '../../../../lib/api';

type Row = { id_producto: number; sku: string; producto: string; cantidad: number; monto: number };

export default async function SalesTopProductsPage({ searchParams }: { searchParams?: Record<string, string> }) {
  const sp = searchParams || {};
  const from = sp.from_date || new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10);
  const to = sp.to_date || new Date().toISOString().slice(0, 10);
  const limit = sp.limit || '20';
  const qs = new URLSearchParams({ from_date: from, to_date: to, limit });

  let items: Row[] = [];
  let error: string | null = null;
  try { items = await apiGet<Row[]>(`/reports/sales/top-products?${qs.toString()}`); } catch (e: any) { error = e?.message || 'Error'; }

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
  const csvUrl = `${apiBase}/reports/sales/top-products.csv?${qs.toString()}`;
  const totalQty = items.reduce((a, r) => a + (r.cantidad || 0), 0);
  const totalAmt = items.reduce((a, r) => a + (r.monto || 0), 0);
  return (
    <div>
      <h1>Top Productos Vendidos</h1>
      <form method="get" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <label>Desde <input type="date" name="from_date" defaultValue={from} /></label>
        <label>Hasta <input type="date" name="to_date" defaultValue={to} /></label>
        <label>Límite <input name="limit" defaultValue={limit} style={{ width: 80 }} /></label>
        <button type="submit">Filtrar</button>
        <a href={csvUrl} target="_blank" rel="noreferrer">Exportar CSV</a>
      </form>
      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}
      <table>
        <thead><tr><th>ID</th><th>SKU</th><th>Producto</th><th style={{ textAlign: 'right' }}>Cantidad</th><th style={{ textAlign: 'right' }}>Monto</th></tr></thead>
        <tbody>
          {items.map((r, i) => (
            <tr key={i}>
              <td>{r.id_producto}</td>
              <td>{r.sku}</td>
              <td>{r.producto}</td>
              <td style={{ textAlign: 'right' }}>{r.cantidad}</td>
              <td style={{ textAlign: 'right' }}>{r.monto.toFixed(2)}</td>
            </tr>
          ))}
          {!items.length && !error && (<tr><td colSpan={5} style={{ padding: 16 }} className="muted">Sin resultados</td></tr>)}
        </tbody>
        <tfoot><tr><td colSpan={3} style={{ textAlign: 'right', fontWeight: 700 }}>Totales</td><td style={{ textAlign: 'right', fontWeight: 700 }}>{totalQty}</td><td style={{ textAlign: 'right', fontWeight: 700 }}>{totalAmt.toFixed(2)}</td></tr></tfoot>
      </table>
      <p style={{ marginTop: 16 }}><Link href="/reports">Volver</Link></p>
    </div>
  );
}

