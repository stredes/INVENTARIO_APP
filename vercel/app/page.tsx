import Link from 'next/link';

export default function HomePage() {
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Inventario App (Landing + Web Skeleton)</h1>
      <p>
        Esta es una landing estática desplegable en Vercel y un punto de partida para
        evolucionar la app de escritorio (Tkinter) hacia una versión web.
      </p>

      <h2>¿Qué incluye?</h2>
      <ul>
        <li>Landing estática lista para Vercel</li>
        <li>Endpoint de salud: <code>/api/health</code></li>
        <li>Página de productos: <Link href="/products">/products</Link> (consume API Python)</li>
        <li>Catálogo PDF: <a href={(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000') + '/reports/catalog.pdf'} target="_blank">descargar</a></li>
      </ul>

      <h2>Siguientes pasos</h2>
      <ol>
        <li>Configurar una base de datos gestionada (PostgreSQL en Neon/Supabase).</li>
        <li>Crear endpoints reales que consulten esa DB.</li>
        <li>Construir vistas Next.js para gestionar productos, compras y ventas.</li>
      </ol>

      <p>
        Revisa el archivo <code>vercel/README.md</code> del repositorio para los pasos de despliegue.
      </p>
    </div>
  );
}
