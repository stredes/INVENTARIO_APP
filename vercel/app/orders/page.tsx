"use client";
import React from 'react';
import Link from 'next/link';
import { apiGet } from '../../lib/api';

type Purchase = { id: number; fecha_compra: string; id_proveedor: number; estado: string; total_compra: number | string };
type Sale = { id: number; fecha_venta: string; id_cliente: number; estado: string; total_venta: number | string };
type Reception = { id: number; id_compra: number; tipo_doc?: string | null; numero_documento?: string | null; fecha: string };

type PurchaseWithDetails = Purchase & { details: { id: number; id_producto: number; cantidad: number; precio_unitario: number | string; subtotal: number | string; product?: { sku: string; nombre: string } }[] };
type SaleWithDetails = Sale & { details: { id: number; id_producto: number; cantidad: number; precio_unitario: number | string; subtotal: number | string; product?: { sku: string; nombre: string } }[] };

export default function OrdersAdminPage() {
  const [tab, setTab] = React.useState<'todas'|'compras'|'ventas'|'recepciones'>('todas');
  const [purchases, setPurchases] = React.useState<Purchase[]>([]);
  const [sales, setSales] = React.useState<Sale[]>([]);
  const [recs, setRecs] = React.useState<Reception[]>([]);
  const [selPurchase, setSelPurchase] = React.useState<PurchaseWithDetails | null>(null);
  const [selSale, setSelSale] = React.useState<SaleWithDetails | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

  React.useEffect(() => {
    (async () => {
      try {
        setError(null);
        const [p, s, r] = await Promise.all([
          apiGet<Purchase[]>(`/purchases`),
          apiGet<Sale[]>(`/sales`),
          apiGet<Reception[]>(`/receptions`),
        ]);
        setPurchases(p); setSales(s); setRecs(r);
      } catch (e: any) { setError(e?.message || 'Error cargando órdenes'); }
    })();
  }, []);

  const loadPurchase = async (id: number) => {
    try { setSelSale(null); setSelPurchase(await apiGet<PurchaseWithDetails>(`/purchases/${id}`)); } catch (e:any){ setError(e?.message || 'Error detalle compra'); }
  };
  const loadSale = async (id: number) => {
    try { setSelPurchase(null); setSelSale(await apiGet<SaleWithDetails>(`/sales/${id}`)); } catch (e:any){ setError(e?.message || 'Error detalle venta'); }
  };

  return (
    <div>
      <h1>Órdenes</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {(['todas','compras','ventas','recepciones'] as const).map(t => (
          <button key={t} className={tab===t? 'btn btn-primary':'btn'} onClick={()=>setTab(t)}>{t[0].toUpperCase()+t.slice(1)}</button>
        ))}
      </div>
      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}

      {(tab==='todas' || tab==='compras') && (
        <div className="card pad" style={{ marginBottom: 16 }}>
          <h3 style={{ marginTop: 0 }}>Compras</h3>
          <div className="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>Fecha</th><th>Proveedor</th><th>Estado</th><th style={{ textAlign:'right' }}>Total</th><th>Acciones</th></tr></thead>
            <tbody>
              {purchases.map(p => (
                <tr key={p.id}>
                  <td>{p.id}</td>
                  <td>{new Date(p.fecha_compra).toLocaleString()}</td>
                  <td>{p.id_proveedor}</td>
                  <td>{p.estado}</td>
                  <td style={{ textAlign:'right' }}>{p.total_compra}</td>
                  <td>
                    <button className="btn" onClick={()=>loadPurchase(p.id)}>Ver detalle</button>
                    <a className="btn" href={`${apiBase}/purchases/${p.id}/pdf`} target="_blank">PDF</a>
                    <Link className="btn" href={`/purchases/${p.id}/receive`}>Recepcionar</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          {selPurchase && (
            <div style={{ marginTop: 12 }}>
              <h4>Detalle OC #{selPurchase.id}</h4>
              <div className="table-wrap">
              <table>
                <thead><tr><th>ID</th><th>SKU</th><th>Producto</th><th style={{textAlign:'right'}}>Cant.</th><th style={{textAlign:'right'}}>P.Unit</th><th style={{textAlign:'right'}}>Subtotal</th></tr></thead>
                <tbody>
                  {selPurchase.details.map(d => (
                    <tr key={d.id}>
                      <td>{d.id_producto}</td><td>{d.product?.sku || ''}</td><td>{d.product?.nombre || ''}</td>
                      <td style={{textAlign:'right'}}>{d.cantidad}</td>
                      <td style={{textAlign:'right'}}>{d.precio_unitario}</td>
                      <td style={{textAlign:'right'}}>{d.subtotal}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </div>
          )}
        </div>
      )}

      {(tab==='todas' || tab==='ventas') && (
        <div className="card pad" style={{ marginBottom: 16 }}>
          <h3 style={{ marginTop: 0 }}>Ventas</h3>
          <div className="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>Fecha</th><th>Cliente</th><th>Estado</th><th style={{ textAlign:'right' }}>Total</th><th>Acciones</th></tr></thead>
            <tbody>
              {sales.map(s => (
                <tr key={s.id}>
                  <td>{s.id}</td>
                  <td>{new Date(s.fecha_venta).toLocaleString()}</td>
                  <td>{s.id_cliente}</td>
                  <td>{s.estado}</td>
                  <td style={{ textAlign:'right' }}>{s.total_venta}</td>
                  <td>
                    <button className="btn" onClick={()=>loadSale(s.id)}>Ver detalle</button>
                    <a className="btn" href={`${apiBase}/sales/${s.id}/pdf`} target="_blank">PDF</a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          {selSale && (
            <div style={{ marginTop: 12 }}>
              <h4>Detalle OV #{selSale.id}</h4>
              <div className="table-wrap">
              <table>
                <thead><tr><th>ID</th><th>SKU</th><th>Producto</th><th style={{textAlign:'right'}}>Cant.</th><th style={{textAlign:'right'}}>P.Unit</th><th style={{textAlign:'right'}}>Subtotal</th></tr></thead>
                <tbody>
                  {selSale.details.map(d => (
                    <tr key={d.id}>
                      <td>{d.id_producto}</td><td>{d.product?.sku || ''}</td><td>{d.product?.nombre || ''}</td>
                      <td style={{textAlign:'right'}}>{d.cantidad}</td>
                      <td style={{textAlign:'right'}}>{d.precio_unitario}</td>
                      <td style={{textAlign:'right'}}>{d.subtotal}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </div>
          )}
        </div>
      )}

      {(tab==='todas' || tab==='recepciones') && (
        <div className="card pad">
          <h3 style={{ marginTop: 0 }}>Recepciones</h3>
          <div className="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>OC</th><th>Tipo</th><th>N°</th><th>Fecha</th><th>PDF</th></tr></thead>
            <tbody>
              {recs.map(r => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>OC-{r.id_compra}</td>
                  <td>{r.tipo_doc || '-'}</td>
                  <td>{r.numero_documento || '-'}</td>
                  <td>{new Date(r.fecha).toLocaleString()}</td>
                  <td><a className="btn" href={`${apiBase}/receptions/${r.id}/pdf`} target="_blank">PDF</a></td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}

      <p style={{ marginTop: 16 }} className="muted"><Link href="/">Volver</Link></p>
    </div>
  );
}
