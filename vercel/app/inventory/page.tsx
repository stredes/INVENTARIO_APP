import { apiGet } from '../../lib/api';
import Link from 'next/link';
import Accordion from '../../components/Accordion';
import LabelPrintForm from '../../components/forms/LabelPrintForm';

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
  if (sp.unidad) qs.set('unidad', sp.unidad);
  if (sp.stock_min) qs.set('stock_min', sp.stock_min);
  if (sp.stock_max) qs.set('stock_max', sp.stock_max);
  if (sp.solo_bajo_minimo) qs.set('solo_bajo_minimo', sp.solo_bajo_minimo);
  if (sp.solo_sobre_maximo) qs.set('solo_sobre_maximo', sp.solo_sobre_maximo);

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
  if (sp.stock_min) xlsxQs.set('stock_min', sp.stock_min);
  if (sp.stock_max) xlsxQs.set('stock_max', sp.stock_max);
  if (sp.solo_bajo_minimo) xlsxQs.set('solo_bajo_minimo', sp.solo_bajo_minimo);
  if (sp.solo_sobre_maximo) xlsxQs.set('solo_sobre_maximo', sp.solo_sobre_maximo);
  const xlsxUrl = `${apiBase}/reports/inventory.xlsx?${xlsxQs.toString()}`;
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Inventario</h1>
      <div className="accordion" style={{ marginBottom: 12 }}>
        <Accordion title="Acciones rápidas">
          <div className="grid-3">
            <Link className="btn" href="/inventory/entries/new">+ Entrada de stock</Link>
            <Link className="btn" href="/inventory/exits/new">- Salida de stock</Link>
            <Link className="btn" href="/inventory/move">↔ Mover stock</Link>
            <Link className="btn" href="/locations">Ubicaciones</Link>
          </div>
        </Accordion>
      </div>
      <div className="accordion" style={{ marginBottom: 12 }}>
        <Accordion title="Filtros" defaultOpen>
          <form method="get" className="grid-4" style={{ alignItems: 'end' }}>
            <label>
              Búsqueda
              <input name="q" placeholder="Nombre o SKU" defaultValue={sp.q || ''} />
            </label>
            <label>
              Proveedor ID
              <input name="supplier_id" placeholder="Ej. 1" defaultValue={sp.supplier_id || ''} />
            </label>
            <label>
              Unidad
              <input name="unidad" placeholder="Ej. U, KG" defaultValue={sp.unidad || ''} />
            </label>
            <div />

            <label>
              Stock mín.
              <input type="number" name="stock_min" placeholder="0" defaultValue={sp.stock_min || ''} />
            </label>
            <label>
              Stock máx.
              <input type="number" name="stock_max" placeholder="9999" defaultValue={sp.stock_max || ''} />
            </label>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input type="checkbox" name="solo_bajo_minimo" value="true" defaultChecked={sp.solo_bajo_minimo === 'true'} />
              Solo bajo mínimo
            </label>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input type="checkbox" name="solo_sobre_maximo" value="true" defaultChecked={sp.solo_sobre_maximo === 'true'} />
              Solo sobre máximo
            </label>

            <div style={{ display: 'flex', gap: 8 }}>
              <button type="submit" className="btn btn-primary">Aplicar</button>
              <a className="btn" href="/inventory">Limpiar</a>
              <a className="btn" href={xlsxUrl} target="_blank" rel="noreferrer">Exportar XLSX</a>
            </div>
          </form>
        </Accordion>

        <Accordion title="Impresión de etiquetas">
          <LabelPrintForm />
        </Accordion>
      </div>
      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}
      <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Nombre</th>
            <th>SKU</th>
            <th style={{ textAlign: 'right' }}>Stock</th>
            <th style={{ textAlign: 'right' }}>Min/Max</th>
            <th>Proveedor</th>
            <th>Ubicación</th>
            <th style={{ textAlign: 'center' }}>Umbral</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id} style={{ background: r.below_min ? '#fff2f2' : undefined }}>
              <td>{r.id}</td>
              <td>{r.nombre}</td>
              <td>{r.sku}</td>
              <td style={{ textAlign: 'right' }}>{r.stock_actual}</td>
              <td style={{ textAlign: 'right' }}>{r.min_threshold ?? 0}/{r.max_threshold ?? 0}</td>
              <td>{r.id_proveedor}</td>
              <td>{r.id_ubicacion ?? '-'}</td>
              <td style={{ textAlign: 'center' }}>
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
      </div>
      <p style={{ marginTop: 24 }}>
        <Link href="/">Volver</Link>
      </p>
    </div>
  );
}
