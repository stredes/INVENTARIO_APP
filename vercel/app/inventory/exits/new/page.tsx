"use client";
import React from 'react';
import Link from 'next/link';
import { apiGet } from '../../../../lib/api';

type Product = { id: number; sku: string; nombre: string };

export default function NewExitPage() {
  const [productKey, setProductKey] = React.useState('');
  const [by, setBy] = React.useState<'sku'|'id'>('sku');
  const [qty, setQty] = React.useState('');
  const [when, setWhen] = React.useState('');
  const [motivo, setMotivo] = React.useState('Salida manual');
  const [err, setErr] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

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
        motivo: motivo || 'Salida manual',
        when: when || null,
      };
      const res = await fetch(`${apiBase}/inventory/exits`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      window.location.href = '/inventory';
    } catch (e: any) { setErr(e?.message || 'Error'); } finally { setLoading(false); }
  };

  return (
    <div>
      <h1>Nueva Salida de Stock</h1>
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
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" disabled={loading} onClick={onSubmit}>Registrar</button>
          <Link className="btn" href="/inventory">Cancelar</Link>
        </div>
      </div>
    </div>
  );
}

