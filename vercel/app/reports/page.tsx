import Link from 'next/link';

export default function ReportsIndex() {
  return (
    <div>
      <h1>Reportes</h1>
      <ul>
        <li><Link href="/reports/sales">Ventas (listado + CSV/PDF)</Link></li>
        <li><Link href="/reports/purchases">Compras (resumen + CSV)</Link></li>
        <li><Link href="/reports/purchases/details">Compras (detalle por ítem)</Link></li>
        <li><Link href="/reports/sales/top-products">Top productos vendidos</Link></li>
      </ul>
    </div>
  );
}

