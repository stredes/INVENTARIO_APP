"use client";
import React from 'react';
import Link from 'next/link';
import { apiGet } from '../../../../lib/api';

type Product = { id: number; sku: string; nombre: string };
type Location = { id: number; nombre: string };

export default function NewEntryPage() {
  const [productKey, setProductKey] = React.useState('');
  const [by, setBy] = React.useState<'sku'|'id'>('sku');
  const [qty, setQty] = React.useState('');
  const [when, setWhen] = React.useState('');
  const [motivo, setMotivo] = React.useState('Ingreso manual');
  const [locId, setLocId] = React.useState('');
  const [lote, setLote] = React.useState('');
  const [serie, setSerie] = React.useState('');
  const [vence, setVence] = React.useState('');
  const [locations, setLocations] = React.useState<Location[]>([]);
  const [err, setErr] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

  React.useEffect(() => { (async ()=>{ try { setLocations(await apiGet<Location[]>(`/locations`)); } catch {} })(); }, []);

  const onSubmit = async () => {
    setErr(null); setLoading(true);
    try {
      let p: Product | null = null;
      if (by === 'sku') p = await apiGet<Product>(`/products/sku/${encodeURIComponent(productKey)}`);
      else p = await apiGet<Product>(`/products/${encodeURIComponent(productKey)}`);
      if (!p) throw new Error('Producto no encontrado');
      const payload = {
        product_id: p.id,
        cantidad: Math.max(1, parseInt(qty || '0')),
        motivo: motivo || 'Ingreso manual',
        when: when || null,
        lote: lote || null,
        serie: serie || null,
        fecha_vencimiento: vence || null,
        reception_id: null,
        location_id: locId ? parseInt(locId) : null,
      };
      const res = await fetch(`${apiBase}/inventory/entries`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      window.location.href = '/inventory';
    } catch (e: any) { setErr(e?.message || 'Error'); } finally { setLoading(false); }
  };

  return (
    <div>
      <h1>Nueva Entrada de Stock</h1>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}
      <div className="card pad" style={{ display: 'grid', gap: 12, maxWidth: 720 }}>
        <div className="grid-3">
          <label>Buscar por
            <select value={by} onChange={(e)=>setBy(e.target.value as any)}><option value="sku">SKU</option><option value="id">ID</option></select>
          </label>
          <label>Producto
            <input value={productKey} onChange={(e)=>setProductKey(e.target.value)} placeholder={by==='sku'?'SKU':'ID'} />
          </label>
          <label>Cantidad
            <input type="number" value={qty} onChange={(e)=>setQty(e.target.value)} placeholder="0" />
          </label>
        </div>
        <div className="grid-3">
          <label>Motivo<input value={motivo} onChange={(e)=>setMotivo(e.target.value)} /></label>
          <label>Fecha<input type="datetime-local" value={when} onChange={(e)=>setWhen(e.target.value)} /></label>
          <label>Ubicación
            <select value={locId} onChange={(e)=>setLocId(e.target.value)}>
              <option value="">(ninguna)</option>
              {locations.map(l => (<option key={l.id} value={l.id}>{l.nombre}</option>))}
            </select>
          </label>
        </div>
        <div className="grid-3">
          <label>Lote<input value={lote} onChange={(e)=>setLote(e.target.value)} /></label>
          <label>Serie<input value={serie} onChange={(e)=>setSerie(e.target.value)} /></label>
          <label>Vence<input type="date" value={vence} onChange={(e)=>setVence(e.target.value)} /></label>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" disabled={loading} onClick={onSubmit}>Registrar</button>
          <Link className="btn" href="/inventory">Cancelar</Link>
        </div>
      </div>
    </div>
  );
}

