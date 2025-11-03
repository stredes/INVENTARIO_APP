"use client";
import React from 'react';
import Link from 'next/link';

export default function ImportProductsPage() {
  const [file, setFile] = React.useState<File | null>(null);
  const [res, setRes] = React.useState<any>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

  const onSubmit = async () => {
    setErr(null); setRes(null); setLoading(true);
    try {
      if (!file) throw new Error('Selecciona un CSV');
      const fd = new FormData(); fd.append('file', file);
      const r = await fetch(`${apiBase}/import/products`, { method: 'POST', body: fd });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setRes(await r.json());
    } catch (e: any) { setErr(e?.message || 'Error'); } finally { setLoading(false); }
  };

  return (
    <div>
      <h1>Importar Productos (CSV)</h1>
      <p className="muted">Cabecera esperada: sku,nombre,precio_compra,precio_venta,stock_actual,id_proveedor,unidad_medida,familia,barcode,id_ubicacion</p>
      <p><a href={`${apiBase}/import/products/sample.csv`} target="_blank" rel="noreferrer">Descargar CSV de ejemplo</a></p>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}
      <div className="card pad" style={{ display:'grid', gap:8, maxWidth: 720 }}>
        <input type="file" accept="text/csv,.csv" onChange={(e)=> setFile(e.target.files?.[0] || null)} />
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-primary" disabled={loading} onClick={onSubmit}>Subir</button>
          <Link className="btn" href="/products">Volver</Link>
        </div>
      </div>
      {res && (
        <div className="card pad" style={{ marginTop: 12 }}>
          <div>Creado: <b>{res.created}</b> — Actualizado: <b>{res.updated}</b></div>
          {res.errors?.length ? (
            <details style={{ marginTop: 8 }}>
              <summary>Errores ({res.errors.length})</summary>
              <pre style={{ whiteSpace:'pre-wrap' }}>{res.errors.join('\n')}</pre>
            </details>
          ) : null}
        </div>
      )}
    </div>
  );
}
