import { apiGet } from '../../lib/api';
import Link from 'next/link';
import Accordion from '../../components/Accordion';
import LocationQuickForm from '../../components/forms/LocationQuickForm';

type Location = { id: number; nombre: string; descripcion?: string | null };

export default async function LocationsPage() {
  let items: Location[] = [];
  let error: string | null = null;
  try { items = await apiGet<Location[]>(`/locations`); } catch (e: any) { error = e?.message || 'Error cargando ubicaciones'; }
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Ubicaciones</h1>
      <div className="accordion" style={{ marginBottom: 12 }}>
        <Accordion title="Ubicación (rápido)" defaultOpen>
          <LocationQuickForm />
        </Accordion>
      </div>
      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}
      <table>
        <thead><tr><th>ID</th><th>Nombre</th><th>Descripción</th><th>Acciones</th></tr></thead>
        <tbody>
          {items.map((l) => (
            <tr key={l.id}>
              <td>{l.id}</td>
              <td>{l.nombre}</td>
              <td>{l.descripcion || '-'}</td>
              <td><Link href={`/locations/${l.id}/edit`}>Editar</Link></td>
            </tr>
          ))}
          {!items.length && !error && (<tr><td colSpan={4} style={{ padding: 16 }} className="muted">Sin ubicaciones</td></tr>)}
        </tbody>
      </table>
      <p style={{ marginTop: 16 }}><Link href="/">Volver</Link></p>
    </div>
  );
}

