"use client";
import { useState } from 'react';
import Link from 'next/link';
import { apiGet, apiPost } from '../../../lib/api';

type Product = { id: number; nombre: string; sku: string; precio_compra: number; id_proveedor: number };

export default function NewPurchasePage() {
  const [supplierId, setSupplierId] = useState('');
  const [errors, setErrors] = useState<string | null>(null);
  const [items, setItems] = useState<{ product?: Product; product_id?: number; cantidad: number; precio_unitario: number }[]>([]);
  const [adding, setAdding] = useState({ key: '', by: 'sku' as 'sku' | 'id', qty: '1' });
  const [loading, setLoading] = useState(false);

  const addItem = async () => {
    setErrors(null);
    try {
      let p: Product | null = null;
      if (adding.by === 'sku') {
        p = await apiGet<Product>(`/products/sku/${encodeURIComponent(adding.key)}`);
      } else {
        p = await apiGet<Product>(`/products/${encodeURIComponent(adding.key)}`);
      }
      if (!p) throw new Error('Producto no encontrado');
      if (supplierId && parseInt(supplierId) !== p.id_proveedor) {
        throw new Error('El producto no pertenece al proveedor seleccionado');
      }
      const qty = Math.max(1, parseInt(adding.qty || '1'));
      setItems([...items, { product: p, product_id: p.id, cantidad: qty, precio_unitario: Number(p.precio_compra) }]);
      setAdding({ ...adding, key: '', qty: '1' });
      if (!supplierId) setSupplierId(String(p.id_proveedor));
    } catch (e: any) {
      setErrors(e?.message || 'Error al agregar');
    }
  };

  const updateItem = (idx: number, patch: Partial<{ cantidad: number; precio_unitario: number }>) => {
    setItems(items.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  };
  const removeItem = (idx: number) => setItems(items.filter((_, i) => i !== idx));

  const total = items.reduce((acc, it) => acc + (it.cantidad * it.precio_unitario), 0);

  const onSubmit = async () => {
    setErrors(null); setLoading(true);
    try {
      if (!supplierId) throw new Error('Debe indicar proveedor');
      if (!items.length) throw new Error('Debe agregar al menos un ítem');
      const payload = {
        supplier_id: parseInt(supplierId),
        items: items.map((it) => ({ product_id: it.product_id, cantidad: it.cantidad, precio_unitario: it.precio_unitario })),
        estado: 'Completada',
        apply_to_stock: true,
      };
      await apiPost('/purchases', payload);
      window.location.href = '/purchases';
    } catch (e: any) {
      setErrors(e?.message || 'Error');
    } finally { setLoading(false); }
  };

  return (
    <div>
      <h1>Nueva Compra</h1>
      {errors && <p style={{ color: 'crimson' }}>Error: {errors}</p>}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
        <label>Proveedor ID <input value={supplierId} onChange={(e) => setSupplierId(e.target.value)} placeholder="ID Proveedor" /></label>
      </div>

      <div style={{ border: '1px solid #eee', padding: 12, borderRadius: 8, marginBottom: 12 }}>
        <strong>Agregar ítem</strong>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <select value={adding.by} onChange={(e) => setAdding({ ...adding, by: e.target.value as any })}>
            <option value="sku">SKU</option>
            <option value="id">ID</option>
          </select>
          <input value={adding.key} onChange={(e) => setAdding({ ...adding, key: e.target.value })} placeholder={adding.by === 'sku' ? 'SKU' : 'ID'} />
          <input value={adding.qty} onChange={(e) => setAdding({ ...adding, qty: e.target.value })} placeholder="Cant." />
          <button onClick={addItem}>Agregar</button>
        </div>
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>Producto</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 8 }}>SKU</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Cantidad</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Precio Unit.</th>
            <th style={{ textAlign: 'right', borderBottom: '1px solid #ddd', padding: 8 }}>Subtotal</th>
            <th style={{ textAlign: 'center', borderBottom: '1px solid #ddd', padding: 8 }}>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it, idx) => (
            <tr key={idx}>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{it.product?.nombre}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8 }}>{it.product?.sku}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>
                <input value={it.cantidad} onChange={(e) => updateItem(idx, { cantidad: parseInt(e.target.value || '0') })} style={{ width: 80, textAlign: 'right' }} />
              </td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>
                <input value={it.precio_unitario} onChange={(e) => updateItem(idx, { precio_unitario: parseFloat(e.target.value || '0') })} style={{ width: 120, textAlign: 'right' }} />
              </td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'right' }}>{(it.cantidad * it.precio_unitario).toFixed(2)}</td>
              <td style={{ borderBottom: '1px solid #eee', padding: 8, textAlign: 'center' }}>
                <button onClick={() => removeItem(idx)} style={{ color: 'crimson' }}>Quitar</button>
              </td>
            </tr>
          ))}
          {!items.length && (
            <tr>
              <td colSpan={6} style={{ padding: 16, color: '#666' }}>Sin ítems</td>
            </tr>
          )}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={4} style={{ padding: 8, textAlign: 'right', fontWeight: 700 }}>Total</td>
            <td style={{ padding: 8, textAlign: 'right', fontWeight: 700 }}>{total.toFixed(2)}</td>
            <td />
          </tr>
        </tfoot>
      </table>

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button disabled={loading} onClick={onSubmit}>Confirmar y Sumar Stock</button>
        <Link href="/purchases">Cancelar</Link>
      </div>
    </div>
  );
}
