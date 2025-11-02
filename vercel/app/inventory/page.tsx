import { apiGet } from '../../lib/api';
import Link from 'next/link';

type Row = {
  id: number;
  nombre: string;
  sku: string;
  stock_actual: number;
  id_proveedor: number;
  id_ubicacion?: number | null;
  familia?: string | null;
  min_threshold?: number | null;
  max_threshold?: number | null;
  below_min?: boolean | null;
};

export default async function InventoryPage({ searchParams }: { searchParams?: Record<string, string> }) {
  const sp = searchParams || {};
  const qs = new URLSearchParams();
  if (sp.q) qs.set('q', sp.q);
  if (sp.supplier_id) qs.set('supplier_id', sp.supplier_id);

  let items: Row[] = [];
  let error: string | null = null;
  try {
    items = await apiGet<Row[]>(`/inventory/stock?${qs.toString()}`);
  } catch (e: any) {
    error = e?.message || 'Error cargando inventario';
  }
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
  const xlsxQs = new URLSearchParams({ report_type: 'venta' });
  if (sp.q) xlsxQs.set('nombre_contains', sp.q);
  const xlsxUrl = `${apiBase}/reports/inventory.xlsx?${xlsxQs.toString()}`;
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Inventario</h1>
      <form method="get" style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input name="q" placeholder="Buscar por nombre/SKU" defaultValue={sp.q || ''} />
        <input name="supplier_id" placeholder="ID Proveedor" defaultValue={sp.supplier_id || ''} />
        <button type="submit">Filtrar</button>
      </form>
      <p><a href={xlsxUrl} target="_blank" rel="noreferrer">Exportar XLSX (venta)</a></p>
      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>ID</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Nombre</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>SKU</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Stock</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Min/Max</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Proveedor</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Ubicación</th>
            <th style={{ textAlign: 'center', borderBottom: '1px solid #ddd', padding: 8 }}>Umbral</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id} style={{ background: r.below_min ? '#fff2f2' : undefined }}>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.id}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.nombre}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.sku}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{r.stock_actual}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{r.min_threshold ?? 0}/{r.max_threshold ?? 0}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.id_proveedor}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.id_ubicacion ?? '-'}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'center' }}>
                <a href={`/inventory/thresholds/${r.id}`}>Editar</a>
              </td>
            </tr>
          ))}
          {!items.length && !error && (
            <tr>
              <td colSpan={7} style={{ padding: 16, color: '#666' }}>Sin resultados</td>
            </tr>
          )}
        </tbody>
      </table>
      <p style={{ marginTop: 24 }}>
        <Link href="/">Volver</Link>
      </p>
    </div>
  );
}
