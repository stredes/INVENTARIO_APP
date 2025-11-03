"use client";
import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Icon, IconTile } from './icons';
import { getApiBase } from '../lib/api';

export default function SiteHeader() {
  const path = usePathname() || '/';
  const apiBase = getApiBase();
  const nav = [
    { href: '/products', label: 'Productos', icon: 'products' as const },
    { href: '/suppliers', label: 'Proveedores', icon: 'suppliers' as const },
    { href: '/customers', label: 'Clientes', icon: 'customers' as const },
    { href: '/purchases', label: 'Compras', icon: 'purchases' as const },
    { href: '/sales', label: 'Ventas', icon: 'sales' as const },
    { href: '/inventory', label: 'Inventario', icon: 'inventory' as const },
    { href: '/orders', label: 'Órdenes', icon: 'orders' as const },
    { href: '/reports', label: 'Informes', icon: 'reports' as const },
    { href: `${apiBase}/reports/catalog.pdf`, label: 'Catálogo', icon: 'label' as const, external: true },
  ];
  const isActive = (href: string) => path === href || (href !== '/' && path.startsWith(href + '/'));
  return (
    <header className="site-header">
      <div className="site-header-inner">
        <div className="brand">Inventario App</div>
        <nav className="site-nav">
          {nav.map((n) => (
            n.external ? (
              <a key={n.href} href={n.href} target="_blank" rel="noreferrer">
                <IconTile><Icon name={n.icon} size={16} /></IconTile>
                {n.label}
              </a>
            ) : (
              <Link key={n.href} href={n.href} className={isActive(n.href) ? 'active' : ''}>
                <IconTile><Icon name={n.icon} size={16} /></IconTile>
                {n.label}
              </Link>
            )
          ))}
        </nav>
        <div style={{ marginLeft: 'auto' }} />
      </div>
    </header>
  );
}
