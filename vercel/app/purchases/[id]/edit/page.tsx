"use client";
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiGet, apiPut, apiPost } from '../../../../lib/api';

type Purchase = {
  id: number;
  estado: string;
  numero_documento?: string | null;
  fecha_documento?: string | null;
  fecha_contable?: string | null;
  fecha_vencimiento?: string | null;
  moneda?: string | null;
  tasa_cambio?: number | string | null;
  unidad_negocio?: string | null;
  proporcionalidad?: string | null;
  atencion?: string | null;
  tipo_descuento?: string | null;
  descuento?: number | string | null;
  ajuste_iva?: number | string | null;
  stock_policy?: string | null;
  referencia?: string | null;
  ajuste_impuesto?: number | string | null;
};

export default function EditPurchasePage() {
  const { id } = useParams() as { id: string };
  const r = useRouter();
  const [form, setForm] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const p = await apiGet<Purchase>(`/purchases/${id}`);
        const toStr = (v: any) => (v == null ? '' : String(v));
        setForm({
          estado: p.estado || '',
          numero_documento: toStr(p.numero_documento),
          fecha_documento: toStr(p.fecha_documento || ''),
          fecha_contable: toStr(p.fecha_contable || ''),
          fecha_vencimiento: toStr(p.fecha_vencimiento || ''),
          moneda: toStr(p.moneda || ''),
          tasa_cambio: toStr(p.tasa_cambio || ''),
          unidad_negocio: toStr(p.unidad_negocio || ''),
          proporcionalidad: toStr(p.proporcionalidad || ''),
          atencion: toStr(p.atencion || ''),
          tipo_descuento: toStr(p.tipo_descuento || ''),
          descuento: toStr(p.descuento || ''),
          ajuste_iva: toStr(p.ajuste_iva || ''),
          stock_policy: toStr(p.stock_policy || ''),
          referencia: toStr(p.referencia || ''),
          ajuste_impuesto: toStr(p.ajuste_impuesto || ''),
        });
      } catch (e: any) {
        setErr(e?.message || 'Error');
      }
    })();
  }, [id]);

  const onChange = (e: any) => setForm({ ...form, [e.target.name]: e.target.value });

  const onSubmit = async (e: any) => {
    e.preventDefault(); setErr(null); setLoading(true);
    try {
      const payload: any = {
        estado: form.estado || null,
        numero_documento: form.numero_documento || null,
        fecha_documento: form.fecha_documento || null,
        fecha_contable: form.fecha_contable || null,
        fecha_vencimiento: form.fecha_vencimiento || null,
        moneda: form.moneda || null,
        tasa_cambio: form.tasa_cambio ? parseFloat(form.tasa_cambio) : null,
        unidad_negocio: form.unidad_negocio || null,
        proporcionalidad: form.proporcionalidad || null,
        atencion: form.atencion || null,
        tipo_descuento: form.tipo_descuento || null,
        descuento: form.descuento ? parseFloat(form.descuento) : null,
        ajuste_iva: form.ajuste_iva ? parseFloat(form.ajuste_iva) : null,
        stock_policy: form.stock_policy || null,
        referencia: form.referencia || null,
        ajuste_impuesto: form.ajuste_impuesto ? parseFloat(form.ajuste_impuesto) : null,
      };
      await apiPut(`/purchases/${id}`, payload);
      r.push('/purchases');
    } catch (e: any) {
      setErr(e?.message || 'Error');
    } finally { setLoading(false); }
  };

  const onComplete = async () => {
    setErr(null); setLoading(true);
    try { await apiPost(`/purchases/${id}/complete`, {}); r.push('/purchases'); }
    catch (e: any) { setErr(e?.message || 'Error completando compra'); }
    finally { setLoading(false); }
  };

  if (!form) return <p>Cargando...</p>;
  return (
    <div>
      <h1>Editar Compra #{id}</h1>
      {err && <p style={{ color: 'crimson' }}>Error: {err}</p>}
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 8, maxWidth: 640 }}>
        <label>Estado
          <select name="estado" value={form.estado} onChange={onChange}>
            <option value="">(sin cambio)</option>
            <option>Pendiente</option>
            <option>Incompleta</option>
            <option>Por pagar</option>
            <option>Completada</option>
            <option>Cancelada</option>
            <option>Eliminada</option>
          </select>
        </label>
        <label>N° Documento
          <input name="numero_documento" value={form.numero_documento} onChange={onChange} />
        </label>
        <label>F. Documento
          <input type="datetime-local" name="fecha_documento" value={form.fecha_documento} onChange={onChange} />
        </label>
        <label>F. Contable
          <input type="datetime-local" name="fecha_contable" value={form.fecha_contable} onChange={onChange} />
        </label>
        <label>F. Vencimiento
          <input type="datetime-local" name="fecha_vencimiento" value={form.fecha_vencimiento} onChange={onChange} />
        </label>
        <label>Moneda
          <input name="moneda" value={form.moneda} onChange={onChange} />
        </label>
        <label>Tasa Cambio
          <input name="tasa_cambio" value={form.tasa_cambio} onChange={onChange} />
        </label>
        <label>Unidad de Negocio
          <input name="unidad_negocio" value={form.unidad_negocio} onChange={onChange} />
        </label>
        <label>Proporcionalidad
          <input name="proporcionalidad" value={form.proporcionalidad} onChange={onChange} />
        </label>
        <label>Atención
          <input name="atencion" value={form.atencion} onChange={onChange} />
        </label>
        <label>Tipo Descuento
          <select name="tipo_descuento" value={form.tipo_descuento} onChange={onChange}>
            <option value="">(ninguno)</option>
            <option>Monto</option>
            <option>Porcentaje</option>
          </select>
        </label>
        <label>Descuento
          <input name="descuento" value={form.descuento} onChange={onChange} />
        </label>
        <label>Ajuste IVA
          <input name="ajuste_iva" value={form.ajuste_iva} onChange={onChange} />
        </label>
        <label>Política de Stock
          <select name="stock_policy" value={form.stock_policy} onChange={onChange}>
            <option value="">(sin cambio)</option>
            <option>Mueve</option>
            <option>No Mueve</option>
          </select>
        </label>
        <label>Referencia
          <input name="referencia" value={form.referencia} onChange={onChange} />
        </label>
        <label>Ajuste impuesto
          <input name="ajuste_impuesto" value={form.ajuste_impuesto} onChange={onChange} />
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <button disabled={loading} type="submit">Guardar</button>
          <button type="button" onClick={onComplete}>Marcar Completada</button>
          <Link href="/purchases">Cancelar</Link>
        </div>
      </form>
    </div>
  );
}

