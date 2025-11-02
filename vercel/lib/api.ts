export function getApiBase(): string {
  // Nota: en Windows/Node a veces 'localhost' resuelve a ::1 (IPv6),
  // mientras Uvicorn escucha en 127.0.0.1 (IPv4) y la conexión falla.
  // Forzamos IPv4 por defecto para evitar "fetch failed".
  const env = process.env.NEXT_PUBLIC_API_BASE_URL;
  const base = env && env.trim().length ? env.trim() : 'http://127.0.0.1:8000';
  return base.replace('localhost', '127.0.0.1');
}

export async function apiGet<T>(path: string): Promise<T> {
  const base = getApiBase();
  const url = `${base}${path}`;
  try {
    const res = await fetch(url, { next: { revalidate: 0 } });
    if (!res.ok) throw new Error(`GET ${url} -> ${res.status}`);
    return res.json();
  } catch (e: any) {
    const cause = e?.cause ? ` (cause: ${e.cause?.code || e.cause})` : '';
    throw new Error(`fetch failed GET ${url}${cause}`);
  }
}

export async function apiPost<T>(path: string, body: any): Promise<T> {
  const base = getApiBase();
  const url = `${base}${path}`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`POST ${url} -> ${res.status}`);
    return res.json();
  } catch (e: any) {
    const cause = e?.cause ? ` (cause: ${e.cause?.code || e.cause})` : '';
    throw new Error(`fetch failed POST ${url}${cause}`);
  }
}

export async function apiPut<T>(path: string, body: any): Promise<T> {
  const base = getApiBase();
  const url = `${base}${path}`;
  try {
    const res = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`PUT ${url} -> ${res.status}`);
    return res.json();
  } catch (e: any) {
    const cause = e?.cause ? ` (cause: ${e.cause?.code || e.cause})` : '';
    throw new Error(`fetch failed PUT ${url}${cause}`);
  }
}

export async function apiDelete(path: string): Promise<void> {
  const base = getApiBase();
  const url = `${base}${path}`;
  try {
    const res = await fetch(url, { method: 'DELETE' });
    if (!res.ok) throw new Error(`DELETE ${url} -> ${res.status}`);
  } catch (e: any) {
    const cause = e?.cause ? ` (cause: ${e.cause?.code || e.cause})` : '';
    throw new Error(`fetch failed DELETE ${url}${cause}`);
  }
}
