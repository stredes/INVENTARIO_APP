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
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
          <button type="button" onClick={onDelete} style={{ color: 'crimson' }}>Eliminar</button>
          <Link href="/products">Cancelar</Link>
        </div>
      </form>
    </div>
  );
}
