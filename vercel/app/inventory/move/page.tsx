"use client";
import React from 'react';
import Link from 'next/link';
import { apiGet } from '../../../lib/api';

type Product = { id: number; sku: string; nombre: string };
type Location = { id: number; nombre: string };

export default function MoveStockPage() {
  const [by, setBy] = React.useState<'sku'|'id'>('sku');
  const [key, setKey] = React.useState('');
  const [product, setProduct] = React.useState<Product | null>(null);
  const [qty, setQty] = React.useState('');
  const [fromLoc, setFromLoc] = React.useState('');
  const [toLoc, setToLoc] = React.useState('');
  const [when, setWhen] = React.useState('');
  const [locations, setLocations] = React.useState<Location[]>([]);
  const [err, setErr] = React.useState<string | null>(null);
  const [ok, setOk] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

  React.useEffect(() => { (async ()=>{ try { setLocations(await apiGet<Location[]>(`/locations`)); } catch {} })(); }, []);

  const findProduct = async () => {
    setErr(null); setOk(null);
    try {
      let p: Product | null = null;
      if (by === 'sku') p = await apiGet<Product>(`/products/sku/${encodeURIComponent(key)}`);
      else p = await apiGet<Product>(`/products/${encodeURIComponent(key)}`);
      setProduct(p);
    } catch (e: any) { setErr(e?.message || 'Producto no encontrado'); setProduct(null); }
  };

  const onSubmit = async () => {
    setErr(null); setOk(null); setLoading(true);
    try {
      if (!product) throw new Error('Busque un producto');
      if (!toLoc) throw new Error('Seleccione ubicación destino');
      const body = { product_id: product.id, qty: Math.max(1, parseInt(qty||'0')), from_location_id: fromLoc? parseInt(fromLoc) : null, to_location_id: parseInt(toLoc), when: when || null };
      const res = await fetch(`${apiBase}/inventory/move`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json(); setOk(data.message || 'OK'); setProduct(null); setKey(''); setQty('');
    } catch (e: any) { setErr(e?.message || 'Error'); } finally { setLoading(false); }
  };

  return (
    <div>
      <h1>Mover Stock</h1>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}
      {ok && <p className="muted">{ok}</p>}
      <div className="card pad" style={{ display:'grid', gap:12, maxWidth: 760 }}>
        <div className="grid-4" style={{ alignItems:'end' }}>
          <label>Buscar por
            <select value={by} onChange={(e)=> setBy(e.target.value as any)}>
              <option value="sku">SKU</option>
              <option value="id">ID</option>
            </select>
          </label>
          <label>Producto
            <input value={key} onChange={(e)=> setKey(e.target.value)} onKeyDown={(e)=>{ if(e.key==='Enter'){ e.preventDefault(); findProduct(); } }} placeholder={by==='sku'?'SKU':'ID'} />
          </label>
          <button className="btn" onClick={findProduct}>Buscar</button>
          <div className="muted">{product ? `${product.sku} — ${product.nombre}` : 'Sin selección'}</div>
        </div>
        <div className="grid-4" style={{ alignItems:'end' }}>
          <label>Cantidad<input type="number" value={qty} onChange={(e)=> setQty(e.target.value)} placeholder="0" /></label>
          <label>Desde (opcional)
            <select value={fromLoc} onChange={(e)=> setFromLoc(e.target.value)}>
              <option value="">(ninguna)</option>
              {locations.map(l => (<option key={l.id} value={l.id}>{l.nombre}</option>))}
            </select>
          </label>
          <label>Hacia
            <select value={toLoc} onChange={(e)=> setToLoc(e.target.value)}>
              <option value="">(elige)</option>
              {locations.map(l => (<option key={l.id} value={l.id}>{l.nombre}</option>))}
            </select>
          </label>
          <label>Fecha<input type="datetime-local" value={when} onChange={(e)=> setWhen(e.target.value)} /></label>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-primary" disabled={loading} onClick={onSubmit}>Registrar traslado</button>
          <Link className="btn" href="/inventory">Volver</Link>
        </div>
      </div>
    </div>
  );
}

