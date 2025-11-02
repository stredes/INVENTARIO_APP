import Link from 'next/link';
import { apiGet } from '../../lib/api';

type Sale = {
  id: number;
  id_cliente: number;
  fecha_venta: string;
  total_venta: number | string;
  estado: string;
};

export default async function SalesPage() {
  let items: Sale[] = [];
  let error: string | null = null;
  try {
    items = await apiGet<Sale[]>(`/sales`);
  } catch (e: any) {
    error = e?.message || 'Error cargando ventas';
  }
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Ventas</h1>
      <p><Link href="/sales/new">+ Nueva venta</Link></p>
      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>ID</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Cliente</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Fecha</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Total</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Estado</th>
            <th style={{ textAlign: 'center', borderBottom: '1px solid #ddd', padding: 8 }}>PDF</th>
            <th style={{ textAlign: 'center', borderBottom: '1px solid #ddd', padding: 8 }}>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.id}>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.id}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.id_cliente}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{new Date(s.fecha_venta).toLocaleString()}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{s.total_venta}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.estado}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'center' }}>
                <a href={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/sales/${s.id}/pdf`} target="_blank">Ver</a>
              </td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'center' }}>
                <form action={`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000'}/sales/${s.id}/cancel?revert_stock=true`} method="post" style={{ display: 'inline' }}>
                  <button type="submit">Cancelar</button>
                </form>
              </td>
            </tr>
          ))}
          {!items.length && !error && (
            <tr>
              <td colSpan={6} style={{ padding: 16, color: '#666' }}>No hay ventas</td>
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
