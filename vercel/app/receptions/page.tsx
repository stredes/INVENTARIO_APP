import { apiGet } from '../../lib/api';
import Link from 'next/link';

type Reception = {
  id: number;
  id_compra: number;
  tipo_doc?: string | null;
  numero_documento?: string | null;
  fecha: string;
};

export default async function ReceptionsPage() {
  let items: Reception[] = [];
  let error: string | null = null;
  try {
    items = await apiGet<Reception[]>(`/receptions`);
  } catch (e: any) {
    error = e?.message || 'Error cargando recepciones';
  }
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Recepciones</h1>
      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>ID</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>OC</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Tipo Doc</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>N°</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Fecha</th>
            <th style={{ textAlign: 'center', borderBottom: '1px solid #ddd', padding: 8 }}>OC PDF</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id}>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.id}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>OC-{r.id_compra}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.tipo_doc || '-'}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.numero_documento || '-'}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{new Date(r.fecha).toLocaleString()}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'center' }}>
                <a href={`${apiBase}/purchases/${r.id_compra}/pdf`} target="_blank">Ver</a>
              </td>
            </tr>
          ))}
          {!items.length && !error && (
            <tr>
              <td colSpan={6} style={{ padding: 16, color: '#666' }}>Sin recepciones</td>
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

