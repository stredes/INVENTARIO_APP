"use client";
import React from 'react';
import { apiPost } from '../../lib/api';

export default function ProductQuickForm() {
  const [form, setForm] = React.useState({
    nombre: '', sku: '', precio_compra: '', precio_venta: '', stock_actual: '0',
    id_proveedor: '', unidad_medida: '', familia: '', barcode: '', image_path: '', id_ubicacion: '',
    iva_percent: '19', margin_percent: '30',
  });
  const [err, setErr] = React.useState<string | null>(null);
  const [ok, setOk] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [imgFile, setImgFile] = React.useState<File | null>(null);
  const [unitBase, setUnitBase] = React.useState('');
  const [unitValue, setUnitValue] = React.useState('');
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
  const toNum = (v: string) => parseFloat(v || '0') || 0;
  const computeSuggested = React.useMemo(() => {
    const cost = toNum(form.precio_compra);
    const iva = toNum(form.iva_percent) / 100;
    const margin = toNum(form.margin_percent) / 100;
    if (cost <= 0) return 0;
    const net = cost * (1 + margin);
    const gross = net * (1 + iva);
    return Math.round(gross * 100) / 100;
  }, [form.precio_compra, form.iva_percent, form.margin_percent]);

  const onChange = (e: any) => setForm({ ...form, [e.target.name]: e.target.value });
  const onSubmit = async (e: any) => {
    e.preventDefault(); setErr(null); setOk(null); setLoading(true);
    try {
      // Subir imagen si hay archivo seleccionado
      let image_path = form.image_path || '';
      if (imgFile) {
        const fd = new FormData();
        fd.append('file', imgFile);
        const res = await fetch((process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000') + '/files/upload', { method: 'POST', body: fd });
        if (!res.ok) throw new Error('Error subiendo imagen');
        const data = await res.json();
        image_path = data.path || image_path;
      }
      const payload = {
        nombre: form.nombre,
        sku: form.sku,
        precio_compra: parseFloat(form.precio_compra || '0'),
        precio_venta: parseFloat(form.precio_venta || '0'),
        stock_actual: parseInt(form.stock_actual || '0'),
        id_proveedor: parseInt(form.id_proveedor),
        unidad_medida: form.unidad_medida || null,
        familia: form.familia || null,
        barcode: form.barcode || null,
        image_path: image_path || null,
        id_ubicacion: form.id_ubicacion ? parseInt(form.id_ubicacion) : null,
      };
      await apiPost('/products', payload);
      setOk('Producto creado');
      setForm({ nombre: '', sku: '', precio_compra: '', precio_venta: '', stock_actual: '0', id_proveedor: '', unidad_medida: '', familia: '', barcode: '', image_path: '', id_ubicacion: '', iva_percent: '19', margin_percent: '30' });
      setImgFile(null); setUnitBase(''); setUnitValue('');
    } catch (e: any) { setErr(e?.message || 'Error'); } finally { setLoading(false); }
  };

  return (
    <form onSubmit={onSubmit} className="grid-3" style={{ alignItems: 'end' }}>
      <label>Nombre<input name="nombre" value={form.nombre} onChange={onChange} required /></label>
      <label>SKU<input name="sku" value={form.sku} onChange={onChange} required /></label>
      <label>ID Proveedor<input name="id_proveedor" value={form.id_proveedor} onChange={onChange} required /></label>
      <label>Precio compra<input name="precio_compra" value={form.precio_compra} onChange={onChange} /></label>
      <label>Precio venta<input name="precio_venta" value={form.precio_venta} onChange={onChange} /></label>
      <label>Stock<input name="stock_actual" value={form.stock_actual} onChange={onChange} /></label>
      <label>IVA %<input name="iva_percent" value={form.iva_percent} onChange={onChange} /></label>
      <label>Margen %<input name="margin_percent" value={form.margin_percent} onChange={onChange} /></label>
      <div style={{ display: 'grid', gap: 6 }}>
        <div className="muted">Sugerido: <strong>{computeSuggested.toFixed(2)}</strong></div>
        <button type="button" className="btn" onClick={() => setForm({ ...form, precio_venta: String(computeSuggested) })}>Usar sugerido</button>
      </div>
      <label>Unidad<input name="unidad_medida" value={form.unidad_medida} onChange={onChange} /></label>
      <label>Familia<input name="familia" value={form.familia} onChange={onChange} /></label>
      <label>Código de barras<input name="barcode" value={form.barcode} onChange={onChange} /></label>
      <label>Imagen (archivo)
        <input type="file" accept="image/*" onChange={(e)=> setImgFile(e.target.files && e.target.files[0] ? e.target.files[0] : null)} />
      </label>
      <label>ID Ubicación<input name="id_ubicacion" value={form.id_ubicacion} onChange={onChange} /></label>
      <div className="grid-3" style={{ gridColumn: '1 / -1', alignItems: 'center' }}>
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
      <div className="card pad" style={{ gridColumn: '1 / -1' }}>
        <strong>Asistente de Unidad</strong>
        <div className="grid-4" style={{ marginTop: 8, alignItems: 'end' }}>
          <label>Base
            <select value={unitBase} onChange={(e)=> setUnitBase(e.target.value)}>
              <option value="">(elige)</option>
              <option value="unidad">unidad</option>
              <option value="caja">caja</option>
              <option value="bolsa">bolsa</option>
              <option value="kg">kg</option>
              <option value="lt">lt</option>
              <option value="ml">ml</option>
            </select>
          </label>
          <label>Valor
            <input value={unitValue} onChange={(e)=> setUnitValue(e.target.value)} placeholder="p.ej. 12" />
          </label>
          <div className="muted">Resultado: <code>{form.unidad_medida || '-'}</code></div>
          <div style={{ display:'flex', gap:8 }}>
            <button type="button" className="btn" onClick={()=>{
              let v = unitBase;
              const n = (unitValue||'').trim();
              if (unitBase === 'caja' || unitBase === 'bolsa') {
                v = n ? `${unitBase} x ${parseInt(n)||''}` : unitBase;
              } else if (unitBase === 'kg' || unitBase === 'lt') {
                v = n ? `${unitBase} ${n}` : unitBase;
              } else if (unitBase === 'ml') {
                v = n ? `${parseInt(n)||''} ml` : 'ml';
              }
              setForm({ ...form, unidad_medida: v });
            }}>Aplicar</button>
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn btn-primary" disabled={loading} type="submit">Agregar</button>
        {ok && <span className="muted">{ok}</span>}
        {err && <span style={{ color: 'crimson' }}>{err}</span>}
      </div>
    </form>
  );
}
