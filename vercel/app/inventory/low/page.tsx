import Link from 'next/link';
import { apiGet } from '../../../lib/api';

type Row = {
  id: number;
  nombre: string;
  sku: string;
  stock_actual: number;
  min_threshold?: number | null;
  max_threshold?: number | null;
  below_min?: boolean | null;
};

export default async function InventoryLowPage({ searchParams }: { searchParams?: Record<string, string> }) {
  const sp = searchParams || {};
  const qs = new URLSearchParams({ solo_bajo_minimo: 'true' });
  if (sp.q) qs.set('q', sp.q);
  if (sp.stock_max) qs.set('stock_max', sp.stock_max);
  let items: Row[] = [];
  let error: string | null = null;
  try {
    items = await apiGet<Row[]>(`/inventory/stock?${qs.toString()}`);
  } catch (e: any) { error = e?.message || 'Error'; }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Bajo mínimos</h1>
      <form method="get" style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <input name="q" placeholder="Buscar por nombre/SKU" defaultValue={sp.q || ''} />
        <input name="stock_max" placeholder="Stock ≤" defaultValue={sp.stock_max || ''} />
        <button type="submit">Filtrar</button>
        <Link className="btn" href="/inventory/low">Limpiar</Link>
      </form>
      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}
      <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Nombre</th>
            <th>SKU</th>
            <th style={{ textAlign:'right' }}>Stock</th>
            <th style={{ textAlign:'right' }}>Min/Max</th>
            <th>Acción</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td>{r.nombre}</td>
              <td>{r.sku}</td>
              <td style={{ textAlign:'right' }}>{r.stock_actual}</td>
              <td style={{ textAlign:'right' }}>{r.min_threshold ?? 0}/{r.max_threshold ?? 0}</td>
              <td><Link href={`/inventory/thresholds/${r.id}`}>Ajustar umbral</Link></td>
            </tr>
          ))}
          {!items.length && !error && (<tr><td colSpan={6} style={{ padding: 16 }} className="muted">Sin resultados</td></tr>)}
        </tbody>
      </table>
      </div>
      <p style={{ marginTop: 16 }}><Link href="/inventory">Volver</Link></p>
    </div>
  );
}

