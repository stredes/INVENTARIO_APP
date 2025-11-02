import Link from 'next/link';
import { apiGet } from '../../lib/api';

type Product = {
  id: number;
  nombre: string;
  sku: string;
  stock_actual: number;
  precio_venta: string | number;
};

export default async function ProductsPage() {
  let items: Product[] = [];
  let error: string | null = null;
  try {
    const data = await apiGet<Product[]>(`/products`);
    items = data;
  } catch (e: any) {
    error = e?.message || 'Error cargando productos';
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Productos</h1>
      <p><Link href="/products/new">+ Nuevo producto</Link></p>
      <p>
        Origen API: <code>{process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}</code>
      </p>
      {error && (
        <p style={{ color: 'crimson' }}>Error: {error}</p>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>ID</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Nombre</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>SKU</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Stock</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Precio Venta</th>
          </tr>
        </thead>
        <tbody>
          {items.map((p) => (
            <tr key={p.id}>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{p.id}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{p.nombre}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{p.sku}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{p.stock_actual}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{p.precio_venta} <a href={`/products/${p.id}/edit`} style={{ marginLeft: 12 }}>Editar</a></td>
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
      <p style={{ marginTop: 24 }}>
        <Link href="/">Volver</Link>
      </p>
    </div>
  );
}
