import Link from 'next/link';
import { apiGet } from '../../lib/api';

type Supplier = {
  id: number;
  razon_social: string;
  rut: string;
  contacto?: string;
  telefono?: string;
  email?: string;
};

export default async function SuppliersPage() {
  let items: Supplier[] = [];
  let error: string | null = null;
  try {
    items = await apiGet<Supplier[]>(`/suppliers`);
  } catch (e: any) {
    error = e?.message || 'Error cargando proveedores';
  }
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Proveedores</h1>
      <p><Link href="/suppliers/new">+ Nuevo proveedor</Link></p>
      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>ID</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Razón Social</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>RUT</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Contacto</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Teléfono</th>
          </tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.id}>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.id}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.razon_social} <a href={`/suppliers/${s.id}/edit`} style={{ marginLeft: 12 }}>Editar</a></td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.rut}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.contacto || '-'}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{s.telefono || '-'}</td>
            </tr>
          ))}
          {!items.length && !error && (
            <tr>
              <td colSpan={5} style={{ padding: 16, color: '#666' }}>No hay proveedores</td>
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
