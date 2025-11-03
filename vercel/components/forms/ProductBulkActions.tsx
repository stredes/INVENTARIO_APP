"use client";
import React from 'react';

export default function ProductBulkActions() {
  const [ids, setIds] = React.useState('');
  const [unidad, setUnidad] = React.useState('');
  const [supplier, setSupplier] = React.useState('');
  const [family, setFamily] = React.useState('');
  const [msg, setMsg] = React.useState<string | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
  const parseIds = () => ids.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
  const doPost = async (path: string, body: any) => {
    setErr(null); setMsg(null); setLoading(true);
    try {
      const res = await fetch(`${apiBase}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setMsg(data.message || 'OK');
      setTimeout(()=> window.location.reload(), 600);
    } catch (e: any) { setErr(e?.message || 'Error'); } finally { setLoading(false); }
  };
  return (
    <div className="grid-4" style={{ alignItems: 'end' }}>
      <label>IDs (coma)
        <input value={ids} onChange={(e)=> setIds(e.target.value)} placeholder="1,2,3" />
      </label>
      <label>Unidad
        <input value={unidad} onChange={(e)=> setUnidad(e.target.value)} placeholder="p.ej. caja x 12" />
      </label>
      <div style={{ display:'flex', gap:8 }}>
        <button className="btn" disabled={loading} onClick={()=> doPost('/products/bulk/unit', { ids: parseIds(), unidad })}>Aplicar Unidad</button>
      </div>
      <div />
      <label>Proveedor ID
        <input value={supplier} onChange={(e)=> setSupplier(e.target.value)} placeholder="Ej. 1" />
      </label>
      <div style={{ display:'flex', gap:8 }}>
        <button className="btn" disabled={loading} onClick={()=> doPost('/products/bulk/supplier', { ids: parseIds(), supplier_id: parseInt(supplier||'0') })}>Aplicar Proveedor</button>
      </div>
      <div />
      <label>Familia
        <input value={family} onChange={(e)=> setFamily(e.target.value)} placeholder="vacío = quitar" />
      </label>
      <div style={{ display:'flex', gap:8 }}>
        <button className="btn" disabled={loading} onClick={()=> doPost('/products/bulk/family', { ids: parseIds(), family: family.trim() || null })}>Aplicar Familia</button>
      </div>
      <div style={{ gridColumn: '1 / -1' }}>
        {msg && <span className="muted">{msg}</span>}
        {err && <span style={{ color: 'crimson' }}>{err}</span>}
      </div>
    </div>
  );
}

