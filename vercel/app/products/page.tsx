import Link from 'next/link';
import { apiGet } from '../../lib/api';
import Accordion from '../../components/Accordion';
import ProductQuickForm from '../../components/forms/ProductQuickForm';
import ProductBulkActions from '../../components/forms/ProductBulkActions';
import LabelPrintForm from '../../components/forms/LabelPrintForm';

type Product = {
  id: number;
  nombre: string;
  sku: string;
  stock_actual: number;
  precio_venta: string | number;
  image_path?: string | null;
  precio_compra: string | number;
  unidad_medida?: string | null;
  barcode?: string | null;
};

export default async function ProductsPage({ searchParams }: { searchParams?: Record<string, string> }) {
  const sp = searchParams || {};
  const qs = new URLSearchParams();
  if (sp.q) qs.set('q', sp.q);
  if (sp.supplier_id) qs.set('supplier_id', sp.supplier_id);
  let items: Product[] = [];
  let error: string | null = null;
  try { items = await apiGet<Product[]>(`/products?${qs.toString()}`); }
  catch (e: any) { error = e?.message || 'Error cargando productos'; }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Productos</h1>
      <div className="accordion">
        <Accordion title="Producto (rápido)" defaultOpen>
          <ProductQuickForm />
        </Accordion>
        <Accordion title="Acciones masivas">
          <ProductBulkActions />
        </Accordion>
        <Accordion title="Filtros">
          <form method="get" className="grid-3" style={{ alignItems: 'end' }}>
            <label>ID<input name="product_id" defaultValue={sp.product_id || ''} placeholder="Ej. 1" /></label>
            <label>Código<input name="q" defaultValue={sp.q || ''} placeholder="SKU o nombre" /></label>
            <label>Proveedor ID<input name="supplier_id" defaultValue={sp.supplier_id || ''} placeholder="Ej. 1" /></label>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" type="submit">Aplicar</button>
              <a className="btn" href="/products">Limpiar</a>
            </div>
          </form>
        </Accordion>
        <Accordion title="Código de barras / Etiquetas">
          <LabelPrintForm />
        </Accordion>
      </div>
      <p>
        Origen API: <code>{process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}</code>
      </p>
      {error && (
        <p style={{ color: 'crimson' }}>Error: {error}</p>
      )}
      <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Imagen</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>ID</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Nombre</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>SKU</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>P. Compra</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>IVA %</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Monto IVA</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>P. + IVA</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Margen %</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Stock</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Precio Venta</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Unidad</th>
            <th style={{ textAlign: 'center', borderBottom: '1px solid #ddd', padding: 8 }}>Etiqueta</th>
          </tr>
        </thead>
        <tbody>
          {items.map((p) => (
            <tr key={p.id}>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>
                {p.image_path ? <img className="thumb" src={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000'}/files/${p.image_path}`} alt="thumb" /> : null}
              </td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{p.id}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{p.nombre}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{p.sku}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{p.precio_compra}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>19</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{(Number(p.precio_compra||0)*0.19).toFixed(0)}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{(Number(p.precio_compra||0)*1.19).toFixed(0)}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{(()=>{ const cost=Number(p.precio_compra||0); const sale=Number(p.precio_venta||0); const net=sale/1.19; return cost>0? (((net-cost)/cost)*100).toFixed(0):'0';})()}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{p.stock_actual}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{p.precio_venta} <a href={`/products/${p.id}/edit`} style={{ marginLeft: 12 }}>Editar</a></td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{p.unidad_medida || '-'}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign:'center' }}>{(p.barcode||p.sku)? '✓' : '-'}</td>
            </tr>
          ))}
          {!items.length && !error && (
            <tr>
              <td colSpan={5} style={{ padding: 16, color: '#666' }}>
                No hay productos
              </td>
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
