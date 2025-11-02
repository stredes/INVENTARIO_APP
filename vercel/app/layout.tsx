export const metadata = {
  title: 'Inventario App',
  description: 'Landing y esqueleto web para Inventario App',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body style={{ fontFamily: 'system-ui, Arial, sans-serif', margin: 0 }}>
        <header style={{ padding: '16px 24px', borderBottom: '1px solid #eee', display: 'flex', gap: 16, alignItems: 'center' }}>
          <strong>Inventario App</strong>
          <nav style={{ display: 'flex', gap: 12, fontSize: 14 }}>
            <a href="/">Inicio</a>
            <a href="/products">Productos</a>
            <a href="/suppliers">Proveedores</a>
            <a href="/customers">Clientes</a>
            <a href="/purchases">Compras</a>
            <a href="/sales">Ventas</a>
            <a href="/inventory">Inventario</a>
            <a href="/receptions">Recepciones</a>
            <a href="/reports/sales">Reporte Ventas</a>
          </nav>
        </header>
        <main style={{ padding: '24px', maxWidth: 960, margin: '0 auto' }}>{children}</main>
        <footer style={{ padding: '24px', borderTop: '1px solid #eee', color: '#666' }}>
          © {new Date().getFullYear()} Inventario App
        </footer>
      </body>
    </html>
  );
}
