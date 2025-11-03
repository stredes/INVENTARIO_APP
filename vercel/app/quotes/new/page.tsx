"use client";
import React from 'react';
import Link from 'next/link';
import { apiGet } from '../../../lib/api';

type Product = { id: number; sku: string; nombre: string; unidad_medida?: string | null; precio_venta?: number | string };

export default function NewQuotePage() {
  const [quoteNo, setQuoteNo] = React.useState<string>(String(Date.now()).slice(-6));
  const [supplier, setSupplier] = React.useState({ nombre: '', contacto: '', telefono: '', direccion: '', pago: '', rut: '' });
  const [lines, setLines] = React.useState<{ id?: number; nombre: string; unidad?: string; cantidad: string; precio: string; dcto?: string }[]>([]);
  const [addBy, setAddBy] = React.useState<'sku'|'id'|'manual'>('sku');
  const [key, setKey] = React.useState('');
  const [qty, setQty] = React.useState('1');
  const [err, setErr] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

  const addItem = async () => {
    setErr(null);
    try {
      let p: Product | null = null;
      if (addBy !== 'manual') {
        if (!key.trim()) throw new Error('Indique un valor');
        if (addBy === 'sku') p = await apiGet<Product>(`/products/sku/${encodeURIComponent(key.trim())}`);
        else p = await apiGet<Product>(`/products/${encodeURIComponent(key.trim())}`);
        if (!p) throw new Error('Producto no encontrado');
      }
      const cantidad = Math.max(1, parseFloat(qty || '1'));
      const precio = p?.precio_venta ? Number(p.precio_venta) : 0;
      setLines([
        ...lines,
        {
          id: p?.id,
          nombre: p ? p.nombre : key.trim(),
          unidad: p?.unidad_medida || 'U',
          cantidad: String(cantidad),
          precio: p ? String(precio) : '0',
        },
      ]);
      setKey(''); setQty('1');
    } catch (e: any) { setErr(e?.message || 'Error al agregar'); }
  };

  const updateLine = (i: number, patch: Partial<{ nombre: string; unidad: string; cantidad: string; precio: string; dcto: string }>) =>
    setLines(lines.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  const removeLine = (i: number) => setLines(lines.filter((_, idx) => idx !== i));

  const subtotal = (l: { cantidad: string; precio: string; dcto?: string }) => {
    const c = parseFloat(l.cantidad || '0') || 0;
    const p = parseFloat(l.precio || '0') || 0;
    const d = parseFloat(l.dcto || '0') || 0;
    const s = c * p;
    return Math.max(0, s - d);
  };
  const total = lines.reduce((a, l) => a + subtotal(l), 0);

  const onGenerate = async () => {
    setErr(null); setLoading(true);
    try {
      if (!lines.length) throw new Error('Agrega al menos un ítem');
      const payload = {
        quote_number: quoteNo || String(Date.now()).slice(-6),
        supplier: supplier,
        items: lines.map((l) => ({
          id: l.id || null,
          nombre: l.nombre,
          unidad: l.unidad || 'U',
          cantidad: parseFloat(l.cantidad || '0') || 0,
          precio: parseFloat(l.precio || '0') || 0,
          dcto: l.dcto ? parseFloat(l.dcto) : null,
          subtotal: subtotal(l),
        })),
        currency: 'CLP',
      };
      const res = await fetch(`${apiBase}/documents/quote.pdf`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (e: any) { setErr(e?.message || 'Error generando PDF'); }
    finally { setLoading(false); }
  };

  return (
    <div>
      <h1>Nueva Cotización</h1>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}
      <div className="card pad" style={{ marginBottom: 12 }}>
        <div className="grid-4">
          <label>N° Cotización<input value={quoteNo} onChange={(e)=>setQuoteNo(e.target.value)} /></label>
          <label>Nombre<input value={supplier.nombre} onChange={(e)=>setSupplier({ ...supplier, nombre: e.target.value })} /></label>
          <label>Contacto<input value={supplier.contacto} onChange={(e)=>setSupplier({ ...supplier, contacto: e.target.value })} /></label>
          <label>Teléfono<input value={supplier.telefono} onChange={(e)=>setSupplier({ ...supplier, telefono: e.target.value })} /></label>
          <label>Dirección<input value={supplier.direccion} onChange={(e)=>setSupplier({ ...supplier, direccion: e.target.value })} /></label>
          <label>Pago<input value={supplier.pago} onChange={(e)=>setSupplier({ ...supplier, pago: e.target.value })} /></label>
          <label>RUT<input value={supplier.rut} onChange={(e)=>setSupplier({ ...supplier, rut: e.target.value })} /></label>
        </div>
      </div>

      <div className="card pad" style={{ marginBottom: 12 }}>
        <strong>Agregar ítem</strong>
        <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <select value={addBy} onChange={(e)=>setAddBy(e.target.value as any)}>
            <option value="sku">SKU</option>
            <option value="id">ID</option>
            <option value="manual">Manual</option>
          </select>
          {addBy !== 'manual' ? (
            <input value={key} onChange={(e)=>setKey(e.target.value)} placeholder={addBy==='sku'? 'SKU' : 'ID'} />
          ) : (
            <input value={key} onChange={(e)=>setKey(e.target.value)} placeholder="Nombre del ítem" />
          )}
          <input value={qty} onChange={(e)=>setQty(e.target.value)} placeholder="Cant." style={{ width: 100 }} />
          <button className="btn" onClick={addItem}>Agregar</button>
        </div>
      </div>

      <table>
        <thead><tr><th>Nombre</th><th>Unidad</th><th style={{textAlign:'right'}}>Cant.</th><th style={{textAlign:'right'}}>Precio</th><th style={{textAlign:'right'}}>Dcto</th><th style={{textAlign:'right'}}>Subtotal</th><th>Acciones</th></tr></thead>
        <tbody>
          {lines.map((l, i) => (
            <tr key={i}>
              <td><input value={l.nombre} onChange={(e)=>updateLine(i, { nombre: e.target.value })} /></td>
              <td><input value={l.unidad || 'U'} onChange={(e)=>updateLine(i, { unidad: e.target.value })} style={{ width: 70 }} /></td>
              <td style={{ textAlign:'right' }}><input value={l.cantidad} onChange={(e)=>updateLine(i, { cantidad: e.target.value })} style={{ width: 100, textAlign:'right' }} /></td>
              <td style={{ textAlign:'right' }}><input value={l.precio} onChange={(e)=>updateLine(i, { precio: e.target.value })} style={{ width: 120, textAlign:'right' }} /></td>
              <td style={{ textAlign:'right' }}><input value={l.dcto || ''} onChange={(e)=>updateLine(i, { dcto: e.target.value })} style={{ width: 120, textAlign:'right' }} /></td>
              <td style={{ textAlign:'right' }}>{subtotal(l).toFixed(2)}</td>
              <td><button className="btn" onClick={()=>removeLine(i)} style={{ color:'crimson' }}>Quitar</button></td>
            </tr>
          ))}
          {!lines.length && (<tr><td colSpan={7} style={{ padding: 16 }} className="muted">Sin ítems</td></tr>)}
        </tbody>
        <tfoot><tr><td colSpan={5} style={{ textAlign:'right', fontWeight:700 }}>Total</td><td style={{ textAlign:'right', fontWeight:700 }}>{total.toFixed(2)}</td><td /></tr></tfoot>
      </table>

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button className="btn btn-primary" disabled={loading} onClick={onGenerate}>Generar PDF</button>
        <Link className="btn" href="/">Volver</Link>
      </div>
    </div>
  );
}

