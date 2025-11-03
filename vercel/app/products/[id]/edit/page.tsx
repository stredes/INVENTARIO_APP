"use client";
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiDelete, apiGet, apiPut } from '../../../../lib/api';

type Product = {
  id: number; nombre: string; sku: string; precio_compra: number | string; precio_venta: number | string; stock_actual: number;
  unidad_medida?: string | null; familia?: string | null; image_path?: string | null; barcode?: string | null;
  id_proveedor: number; id_ubicacion?: number | null;
};

export default function EditProductPage() {
  const { id } = useParams() as { id: string };
  const r = useRouter();
  const [form, setForm] = useState<any>(null);
  const [imgFile, setImgFile] = useState<File | null>(null);
  const [iva, setIva] = useState('19');
  const [margin, setMargin] = useState('30');
  const toNum = (v: string) => parseFloat(v || '0') || 0;
  const suggested = (() => {
    if (!form) return 0;
    const cost = toNum(String(form.precio_compra||'0'));
    const ivaP = toNum(iva)/100; const mP = toNum(margin)/100;
    if (cost<=0) return 0; const net = cost*(1+mP); const gross = net*(1+ivaP);
    return Math.round(gross*100)/100;
  })();
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
  const [suppliers, setSuppliers] = useState<Array<{id:number; razon_social:string}>>([]);
  const [locations, setLocations] = useState<Array<{id:number; nombre:string}>>([]);
  useEffect(()=>{ (async()=>{ try{
    const s = await fetch(`${apiBase}/suppliers`); if(s.ok) setSuppliers(await s.json());
    const l = await fetch(`${apiBase}/locations`); if(l.ok) setLocations(await l.json());
  }catch{}})(); },[apiBase]);

  useEffect(() => {
    (async () => {
      try { const p = await apiGet<Product>(`/products/${id}`); setForm({
        nombre: p.nombre,
        sku: p.sku,
        precio_compra: String(p.precio_compra),
        precio_venta: String(p.precio_venta),
        stock_actual: String(p.stock_actual),
        unidad_medida: p.unidad_medida || '',
        familia: p.familia || '',
        image_path: p.image_path || '',
        barcode: p.barcode || '',
        id_proveedor: String(p.id_proveedor),
        id_ubicacion: p.id_ubicacion ? String(p.id_ubicacion) : '',
      }); } catch (e: any) { setErr(e?.message || 'Error'); }
    })();
  }, [id]);

  const onChange = (e: any) => setForm({ ...form, [e.target.name]: e.target.value });

  const onSubmit = async (e: any) => {
    e.preventDefault(); setErr(null); setLoading(true);
    try {
      let image_path = form.image_path || '';
      if (imgFile) {
        const fd = new FormData(); fd.append('file', imgFile);
        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
        const res = await fetch(`${apiBase}/files/upload`, { method: 'POST', body: fd });
        if (!res.ok) throw new Error('Error subiendo imagen');
        const data = await res.json(); image_path = data.path || image_path;
      }
      const payload = {
        nombre: form.nombre,
        sku: form.sku,
        precio_compra: parseFloat(form.precio_compra || '0'),
        precio_venta: parseFloat(form.precio_venta || '0'),
        stock_actual: parseInt(form.stock_actual || '0'),
        unidad_medida: form.unidad_medida || null,
        familia: form.familia || null,
        image_path: image_path || null,
        barcode: form.barcode || null,
        id_proveedor: parseInt(form.id_proveedor),
        id_ubicacion: form.id_ubicacion ? parseInt(form.id_ubicacion) : null,
      };
      await apiPut(`/products/${id}`, payload);
      r.push('/products');
    } catch (e: any) {
      setErr(e?.message || 'Error');
    } finally { setLoading(false); }
  };

  const onDelete = async () => {
    if (!confirm('¿Eliminar producto?')) return;
    try { await apiDelete(`/products/${id}`); r.push('/products'); }
    catch (e: any) { setErr(e?.message || 'Error'); }
  };

  if (!form) return <p>Cargando...</p>;

  return (
    <div>
      <h1>Editar Producto #{id}</h1>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 8, maxWidth: 720 }}>
        <input required name="nombre" placeholder="Nombre" value={form.nombre} onChange={onChange} />
        <input required name="sku" placeholder="SKU" value={form.sku} onChange={onChange} />
        <input required name="precio_compra" placeholder="Precio compra" value={form.precio_compra} onChange={onChange} />
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 }}>
          <input required name="precio_venta" placeholder="Precio venta" value={form.precio_venta} onChange={onChange} />
          <div className="muted" style={{ display:'flex', alignItems:'center', gap:8 }}>
            IVA % <input value={iva} onChange={(e)=>setIva(e.target.value)} style={{ width:70 }} />
            Margen % <input value={margin} onChange={(e)=>setMargin(e.target.value)} style={{ width:70 }} />
            Sugerido: <strong>{suggested.toFixed(2)}</strong>
            <button type="button" className="btn" onClick={()=> setForm({ ...form, precio_venta: String(suggested) })}>Usar</button>
          </div>
        </div>
        <input required name="stock_actual" placeholder="Stock" value={form.stock_actual} onChange={onChange} />
        <input name="unidad_medida" placeholder="Unidad medida (ej: U)" value={form.unidad_medida} onChange={onChange} />
        <input name="familia" placeholder="Familia" value={form.familia} onChange={onChange} />
        <input type="file" accept="image/*" onChange={(e)=> setImgFile(e.target.files && e.target.files[0] ? e.target.files[0] : null)} />
        <div className="grid-3" style={{ alignItems:'center' }}>
          <div>
            <div className="muted">Preview imagen</div>
            {imgFile ? (
              <img className="thumb" src={URL.createObjectURL(imgFile)} alt="preview" />
            ) : (
              form.image_path ? <img className="thumb" src={`${apiBase}/files/${form.image_path}`} alt="preview" /> : <div className="muted">Sin imagen</div>
            )}
          </div>
          <div>
            <div className="muted">Código de barras</div>
            {((form.barcode||'').trim() || (form.sku||'').trim()) ? (
              <img className="thumb" style={{ background:'#fff', padding:4 }} src={`${apiBase}/labels/barcode.png?code=${encodeURIComponent((form.barcode||form.sku))}&symbology=${(form.barcode||'').length===13?'ean13':'code128'}`} alt="barcode" />
            ) : (
              <div className="muted">Escribe SKU o barcode</div>
            )}
          </div>
        </div>
        <input name="barcode" placeholder="Código de barras" value={form.barcode} onChange={onChange} />
        <label>Proveedor
          <select name="id_proveedor" value={form.id_proveedor} onChange={onChange} required>
            <option value="">(elige)</option>
            {suppliers.map(s => (<option key={s.id} value={s.id}>{s.razon_social}</option>))}
          </select>
        </label>
        <label>Ubicación
          <select name="id_ubicacion" value={form.id_ubicacion} onChange={onChange}>
            <option value="">(ninguna)</option>
            {locations.map(l => (<option key={l.id} value={l.id}>{l.nombre}</option>))}
          </select>
        </label>
        <a className="btn" href="/locations">Admin. ubicaciones…</a>
        <div style={{ display: 'flex', gap: 8 }}>
          <button disabled={loading} type="submit">Guardar</button>
          <button type="button" onClick={onDelete} style={{ color: 'crimson' }}>Eliminar</button>
          <Link href="/products">Cancelar</Link>
        </div>
        <div>
          <button type="button" className="btn" onClick={async ()=>{
            try {
              const body = { code: form.barcode || form.sku, text: form.nombre, symbology: (form.barcode? 'ean13':'code128') };
              const res = await fetch(`${apiBase}/labels/barcode.pdf`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
              if (!res.ok) throw new Error('HTTP '+res.status);
              const blob = await res.blob(); const url = URL.createObjectURL(blob); window.open(url, '_blank'); setTimeout(()=> URL.revokeObjectURL(url), 5000);
            } catch (e) { console.error(e); }
          }}>Imprimir etiqueta</button>
        </div>
      </form>
    </div>
  );
}
