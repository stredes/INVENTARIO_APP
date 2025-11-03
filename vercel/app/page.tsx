import Link from 'next/link';
import DecorVideo from '../components/DecorVideo';
import { Icon, IconTile } from '../components/icons';

export default function HomePage() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
  return (
    <div>
      <h1>Bienvenido</h1>
      <p className="muted">Accesos rápidos a módulos y reportes. Expande un acordeón para ver opciones.</p>

      <div className="home-grid" style={{ display: 'grid', gridTemplateColumns: 'clamp(480px, 34vw, 560px) 1fr', gap: 24, alignItems: 'start', marginBottom: 16 }}>
        <div>
          <DecorVideo className="decor-col decor-left" />
        </div>
        <div>
          <div className="accordion">
            <details open>
              <summary><IconTile className="icon-inline"><Icon name="products" size={16} /></IconTile> Productos</summary>
              <div className="content link-list">
                <Link href="/products">Listado</Link>
                <Link href="/products/new">Nuevo producto</Link>
                <a href={`${apiBase}/reports/catalog.pdf`} target="_blank">Catálogo PDF</a>
              </div>
            </details>

        <details>
          <summary><IconTile className="icon-inline"><Icon name="suppliers" size={16} /></IconTile> Proveedores</summary>
          <div className="content link-list">
            <Link href="/suppliers">Listado</Link>
            <Link href="/suppliers/new">Nuevo proveedor</Link>
          </div>
        </details>

        <details>
          <summary><IconTile className="icon-inline"><Icon name="customers" size={16} /></IconTile> Clientes</summary>
          <div className="content link-list">
            <Link href="/customers">Listado</Link>
            <Link href="/customers/new">Nuevo cliente</Link>
          </div>
        </details>

        <details>
          <summary><IconTile className="icon-inline"><Icon name="purchases" size={16} /></IconTile> Compras</summary>
          <div className="content link-list">
            <Link href="/purchases">Listado</Link>
            <Link href="/purchases/new">Nueva compra</Link>
            <Link href="/receptions">Recepciones</Link>
            <Link href="/orders">Órdenes (admin)</Link>
          </div>
        </details>

        <details>
          <summary><IconTile className="icon-inline"><Icon name="sales" size={16} /></IconTile> Ventas</summary>
          <div className="content link-list">
            <Link href="/sales">Listado</Link>
            <Link href="/sales/new">Nueva venta</Link>
          </div>
        </details>

        <details>
          <summary><IconTile className="icon-inline"><Icon name="inventory" size={16} /></IconTile> Inventario</summary>
          <div className="content link-list">
            <Link href="/inventory">Ver inventario</Link>
            <Link href="/inventory/entries/new">+ Entrada de stock</Link>
            <Link href="/inventory/exits/new">- Salida de stock</Link>
            <Link href="/locations">Ubicaciones</Link>
            <a href={`${apiBase}/reports/inventory.xlsx`} target="_blank">Exportar XLSX</a>
          </div>
        </details>

        <details>
          <summary><IconTile className="icon-inline"><Icon name="reports" size={16} /></IconTile> Reportes</summary>
          <div className="content link-list">
            <Link href="/reports/sales">Ventas</Link>
            <Link href="/reports/purchases">Compras (resumen)</Link>
            <Link href="/reports/purchases/details">Compras (detalle)</Link>
            <Link href="/reports/sales/top-products">Top productos</Link>
          </div>
        </details>
          </div>
        </div>
      </div>
    </div>
  );
}
