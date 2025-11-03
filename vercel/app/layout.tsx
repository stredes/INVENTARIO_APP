import './globals.css';
import SiteHeader from '../components/SiteHeader';

export const metadata = {
  title: 'Inventario App',
  description: 'Landing y esqueleto web para Inventario App',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet" />
      </head>
      <body>
        <SiteHeader />
        <main className="container">{children}</main>
        <footer className="site-footer">
          <div className="site-footer-inner">© {new Date().getFullYear()} Inventario App</div>
        </footer>
      </body>
    </html>
  );
}
