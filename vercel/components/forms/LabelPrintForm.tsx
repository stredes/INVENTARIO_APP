"use client";
import React from 'react';

export default function LabelPrintForm() {
  const [form, setForm] = React.useState({ code: '', text: '', symbology: 'code128', label_w_mm: '50', label_h_mm: '30', copies: '1' });
  const [err, setErr] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
  const onChange = (e: any) => setForm({ ...form, [e.target.name]: e.target.value });
  const onSubmit = async (e: any) => {
    e.preventDefault(); setErr(null); setLoading(true);
    try {
      const res = await fetch(`${apiBase}/labels/barcode.pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: form.code,
          text: form.text || null,
          symbology: form.symbology,
          label_w_mm: parseFloat(form.label_w_mm || '50'),
          label_h_mm: parseFloat(form.label_h_mm || '30'),
          copies: parseInt(form.copies || '1'),
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      setTimeout(()=> URL.revokeObjectURL(url), 5000);
    } catch (e: any) { setErr(e?.message || 'Error'); } finally { setLoading(false); }
  };
  return (
    <form onSubmit={onSubmit} className="grid-4" style={{ alignItems: 'end' }}>
      <label>Código<input name="code" value={form.code} onChange={onChange} placeholder="SKU o código" required /></label>
      <label>Texto<input name="text" value={form.text} onChange={onChange} placeholder="Texto opcional" /></label>
      <label>Símbolo
        <select name="symbology" value={form.symbology} onChange={onChange}>
          <option value="code128">Code128</option>
          <option value="ean13">EAN-13</option>
        </select>
      </label>
      <label>Copias<input name="copies" value={form.copies} onChange={onChange} /></label>
      <label>Ancho (mm)<input name="label_w_mm" value={form.label_w_mm} onChange={onChange} /></label>
      <label>Alto (mm)<input name="label_h_mm" value={form.label_h_mm} onChange={onChange} /></label>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn btn-primary" disabled={loading} type="submit">Imprimir</button>
        {err && <span style={{ color: 'crimson' }}>{err}</span>}
      </div>
    </form>
  );
}

