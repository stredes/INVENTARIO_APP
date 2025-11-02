import Link from 'next/link';
import { apiGet } from '../../lib/api';

type Purchase = {
  id: number;
  id_proveedor: number;
  fecha_compra: string;
  total_compra: number | string;
  estado: string;
};

export default async function PurchasesPage() {
  let items: Purchase[] = [];
  let error: string | null = null;
  try {
    items = await apiGet<Purchase[]>(`/purchases`);
  } catch (e: any) {
    error = e?.message || 'Error cargando compras';
  }
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Compras</h1>
      <p><Link href="/purchases/new">+ Nueva compra</Link></p>
      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
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
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{p.estado} <a href={`/purchases/${p.id}/receive`} style={{ marginLeft: 12 }}>Recepcionar</a></td>
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
      <p style={{ marginTop: 24 }}>
        <Link href="/">Volver</Link>
      </p>
    </div>
  );
}
