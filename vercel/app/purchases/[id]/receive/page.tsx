"use client";
import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { apiGet, apiPost } from '../../../../lib/api';

type Detail = { id: number; id_producto: number; cantidad: number; received_qty: number; product?: { nombre?: string; sku?: string } };
type Purchase = { id: number; id_proveedor: number; fecha_compra: string; estado: string; details: Detail[] };
type Reception = { id: number; id_compra: number; tipo_doc?: string | null; numero_documento?: string | null; fecha: string };

export default function ReceivePurchasePage() {
  const { id } = useParams() as { id: string };
  const [pur, setPur] = useState<Purchase | null>(null);
  const [recs, setRecs] = useState<Reception[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [header, setHeader] = useState({ tipo_doc: 'Factura', numero_documento: '', fecha: '' });
  const [applyStock, setApplyStock] = useState(true);
  const [updateStatus, setUpdateStatus] = useState(true);
  const [defaultLocation, setDefaultLocation] = useState('');
  const [lines, setLines] = useState<Record<number, { qty: string; id_ubicacion?: string; lote?: string; serie?: string; fecha_vencimiento?: string }>>({});
  const [scan, setScan] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const p = await apiGet<Purchase>(`/purchases/${id}`);
        setPur(p);
        const init: any = {};
        for (const d of p.details) {
          const remaining = Math.max(0, (d.cantidad || 0) - (d.received_qty || 0));
          init[d.id_producto] = { qty: remaining ? String(remaining) : '' };
        }
        setLines(init);
        try { setRecs(await apiGet<Reception[]>(`/purchases/${id}/receptions`)); } catch {}
      } catch (e: any) {
        setErr(e?.message || 'Error cargando compra');
      }
    })();
  }, [id]);

  const setLine = (pid: number, patch: any) => setLines({ ...lines, [pid]: { ...(lines[pid] || {}), ...patch } });

  const totals = useMemo(() => {
    if (!pur) return { remaining: 0, toReceive: 0 };
    let remaining = 0, toReceive = 0;
    for (const d of pur.details) {
      remaining += Math.max(0, (d.cantidad || 0) - (d.received_qty || 0));
      const l = lines[d.id_producto] || {};
      toReceive += Math.max(0, parseInt(l.qty || '0') || 0);
    }
    return { remaining, toReceive };
  }, [pur, lines]);

  const fillAllRemaining = () => {
    if (!pur) return;
    const m: any = { ...lines };
    for (const d of pur.details) {
      const remaining = Math.max(0, (d.cantidad || 0) - (d.received_qty || 0));
      m[d.id_producto] = { ...(m[d.id_producto] || {}), qty: remaining ? String(remaining) : '' };
    }
    setLines(m);
  };

  const applyDefaultLocation = () => {
    if (!pur || !defaultLocation) return;
    const m: any = { ...lines };
    for (const d of pur.details) {
      const cur = m[d.id_producto] || {};
      if (!cur.id_ubicacion) cur.id_ubicacion = defaultLocation;
      m[d.id_producto] = cur;
    }
    setLines(m);
  };

  const onScan = () => {
    if (!pur) return;
    const code = scan.trim(); if (!code) return;
    setScan('');
    const found = pur.details.find(d => (d.product?.sku || '').toLowerCase() === code.toLowerCase());
    if (!found) return;
    const remaining = Math.max(0, (found.cantidad || 0) - (found.received_qty || 0));
    if (remaining <= 0) return;
    const current = lines[found.id_producto] || {};
    const currQty = parseInt(current.qty || '0') || 0;
    const newQty = Math.min(remaining, currQty + 1);
    setLines({ ...lines, [found.id_producto]: { ...current, qty: String(newQty) } });
  };

  const validate = () => {
    if (!pur) throw new Error('Compra no cargada');
    for (const d of pur.details) {
      const l = lines[d.id_producto] || {};
      const qty = parseInt(l.qty || '0') || 0;
      const remaining = Math.max(0, (d.cantidad || 0) - (d.received_qty || 0));
      if (qty < 0) throw new Error(`Cantidad inválida en producto ${d.product?.sku || d.id_producto}`);
      if (qty > remaining) throw new Error(`Excede lo restante en ${d.product?.sku || d.id_producto}. Queda ${remaining}`);
      if ((l.lote || '').trim() && (l.serie || '').trim()) throw new Error(`Lote y Serie no pueden usarse juntos (${d.product?.sku || d.id_producto})`);
    }
  };

  const onSubmit = async () => {
    setErr(null); setLoading(true);
    try {
      validate();
      if (!pur) throw new Error('Compra no cargada');
      const items: any[] = [];
      for (const d of pur.details) {
        const l = lines[d.id_producto] || {};
        const qty = parseInt(l.qty || '0');
        if (qty > 0) {
          items.push({
            product_id: d.id_producto,
            received_qty: qty,
            id_ubicacion: l.id_ubicacion ? parseInt(l.id_ubicacion) : null,
            lote: l.lote || null,
            serie: l.serie || null,
            fecha_vencimiento: l.fecha_vencimiento || null,
          });
        }
      }
      if (!items.length) throw new Error('No hay cantidades para recepcionar');

      const payload = {
        purchase_id: pur.id,
        tipo_doc: header.tipo_doc || null,
        numero_documento: header.numero_documento || null,
        fecha: header.fecha || null,
        items,
        apply_to_stock: !!applyStock,
        update_status: !!updateStatus,
      };
      await apiPost('/receptions', payload);
      window.location.href = '/purchases';
    } catch (e: any) {
      setErr(e?.message || 'Error al recepcionar');
    } finally { setLoading(false); }
  };

  if (!pur) return <p>Cargando...</p>;
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
  return (
    <div>
      <h1>Recepcionar Compra #{pur.id}</h1>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}

      <div className="card pad" style={{ marginBottom: 12 }}>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:8, alignItems:'end' }}>
          <label>Escáner SKU
            <input value={scan} onChange={(e)=> setScan(e.target.value)} onKeyDown={(e)=>{ if(e.key==='Enter'){ e.preventDefault(); onScan(); } }} placeholder="Escanee SKU y Enter" />
          </label>
          <label>Ubicación por defecto
            <input value={defaultLocation} onChange={(e)=> setDefaultLocation(e.target.value)} placeholder="ID ubicación" />
          </label>
          <div style={{ display:'flex', gap:8 }}>
            <button className="btn" onClick={applyDefaultLocation}>Aplicar ubicación</button>
            <button className="btn" onClick={fillAllRemaining}>Llenar restantes</button>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        <label>Tipo doc
          <select value={header.tipo_doc} onChange={(e) => setHeader({ ...header, tipo_doc: e.target.value })}>
            <option>Factura</option>
            <option>Guía</option>
            <option>Otro</option>
          </select>
        </label>
        <label>Número
          <input value={header.numero_documento} onChange={(e) => setHeader({ ...header, numero_documento: e.target.value })} placeholder="N° documento" />
        </label>
        <label>Fecha
          <input type="datetime-local" value={header.fecha} onChange={(e) => setHeader({ ...header, fecha: e.target.value })} />
        </label>
        <label>
          <input type="checkbox" checked={applyStock} onChange={(e) => setApplyStock(e.target.checked)} /> Aplicar a stock
        </label>
        <label>
          <input type="checkbox" checked={updateStatus} onChange={(e) => setUpdateStatus(e.target.checked)} /> Actualizar estado OC
        </label>
      </div>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
        <button onClick={fillAllRemaining}>Recibir todo lo restante</button>
        <label>Ubicación por defecto
          <input value={defaultLocation} onChange={(e) => setDefaultLocation(e.target.value)} placeholder="ID ubicación" />
        </label>
        <button onClick={applyDefaultLocation}>Aplicar</button>
        <span style={{ marginLeft: 'auto' }}>Restante total: <b>{totals.remaining}</b> | A recepcionar: <b>{totals.toReceive}</b></span>
      </div>

      <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Producto</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>SKU</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Pedido</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Recibido</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Restante</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Recibir</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Ubicación</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Lote</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Serie</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Vence</th>
          </tr>
        </thead>
        <tbody>
          {pur.details.map((d) => {
            const remaining = Math.max(0, (d.cantidad || 0) - (d.received_qty || 0));
            const l = lines[d.id_producto] || {};
            return (
              <tr key={d.id}>
                <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{d.product?.nombre || d.id_producto}</td>
                <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{d.product?.sku || ''}</td>
                <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{d.cantidad}</td>
                <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{d.received_qty || 0}</td>
                <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{remaining}</td>
                <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>
                  <input value={l.qty || ''} onChange={(e) => setLine(d.id_producto, { qty: e.target.value })} style={{ width: 80, textAlign: 'right' }} />
                </td>
                <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>
                  <input value={l.id_ubicacion || ''} onChange={(e) => setLine(d.id_producto, { id_ubicacion: e.target.value })} placeholder="ID Ubicación" style={{ width: 120 }} />
                </td>
                <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>
                  <input value={l.lote || ''} onChange={(e) => setLine(d.id_producto, { lote: e.target.value, serie: '' })} placeholder="Lote" />
                </td>
                <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>
                  <input value={l.serie || ''} onChange={(e) => setLine(d.id_producto, { serie: e.target.value, lote: '' })} placeholder="Serie" />
                </td>
                <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>
                  <input type="date" value={l.fecha_vencimiento || ''} onChange={(e) => setLine(d.id_producto, { fecha_vencimiento: e.target.value })} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>

      <div style={{ marginTop: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
        <button disabled={loading} onClick={onSubmit}>Registrar Recepción</button>
        <Link href="/purchases">Cancelar</Link>
        <span style={{ marginLeft: 'auto' }}>OC PDF: <a href={`${apiBase}/purchases/${pur.id}/pdf`} target="_blank">Ver</a></span>
      </div>

      {recs.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h3>Recepciones Anteriores</h3>
          <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>ID</th>
                <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Tipo</th>
                <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>N°</th>
                <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Fecha</th>
              </tr>
            </thead>
            <tbody>
              {recs.map((r) => (
                <tr key={r.id}>
                  <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.id}</td>
                  <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.tipo_doc || '-'}</td>
                  <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{r.numero_documento || '-'}</td>
                  <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{new Date(r.fecha).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}
    </div>
  );
}
