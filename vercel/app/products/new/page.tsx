"use client";
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiPost } from '../../../lib/api';

export default function NewProductPage() {
  const r = useRouter();
  const [form, setForm] = useState({
    nombre: '', sku: '', precio_compra: '0', precio_venta: '0', stock_actual: '0',
    unidad_medida: '', familia: '', image_path: '', barcode: '', id_proveedor: '', id_ubicacion: ''
  });
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onChange = (e: any) => setForm({ ...form, [e.target.name]: e.target.value });

  const onSubmit = async (e: any) => {
    e.preventDefault(); setErr(null); setLoading(true);
    try {
      const payload = {
        nombre: form.nombre,
        sku: form.sku,
        precio_compra: parseFloat(form.precio_compra || '0'),
        precio_venta: parseFloat(form.precio_venta || '0'),
        stock_actual: parseInt(form.stock_actual || '0'),
        unidad_medida: form.unidad_medida || null,
        familia: form.familia || null,
        image_path: form.image_path || null,
        barcode: form.barcode || null,
        id_proveedor: parseInt(form.id_proveedor),
        id_ubicacion: form.id_ubicacion ? parseInt(form.id_ubicacion) : null,
      };
      await apiPost('/products', payload);
      r.push('/products');
    } catch (e: any) {
      setErr(e?.message || 'Error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1>Nuevo Producto</h1>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 8, maxWidth: 520 }}>
        <input required name="nombre" placeholder="Nombre" value={form.nombre} onChange={onChange} />
        <input required name="sku" placeholder="SKU" value={form.sku} onChange={onChange} />
        <input required name="precio_compra" placeholder="Precio compra" value={form.precio_compra} onChange={onChange} />
        <input required name="precio_venta" placeholder="Precio venta" value={form.precio_venta} onChange={onChange} />
        <input required name="stock_actual" placeholder="Stock" value={form.stock_actual} onChange={onChange} />
        <input name="unidad_medida" placeholder="Unidad medida (ej: U)" value={form.unidad_medida} onChange={onChange} />
        <input name="familia" placeholder="Familia" value={form.familia} onChange={onChange} />
        <input name="image_path" placeholder="Ruta imagen" value={form.image_path} onChange={onChange} />
        <input name="barcode" placeholder="Código de barras" value={form.barcode} onChange={onChange} />
        <input required name="id_proveedor" placeholder="ID Proveedor" value={form.id_proveedor} onChange={onChange} />
        <input name="id_ubicacion" placeholder="ID Ubicación (opcional)" value={form.id_ubicacion} onChange={onChange} />
        <div style={{ display: 'flex', gap: 8 }}>
          <button disabled={loading} type="submit">Guardar</button>
          <Link href="/products">Cancelar</Link>
        </div>
      </form>
    </div>
  );
}

