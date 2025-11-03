"use client";
import React from 'react';

type IconName =
  | 'home' | 'products' | 'suppliers' | 'customers' | 'purchases' | 'sales'
  | 'inventory' | 'receptions' | 'orders' | 'reports' | 'locations' | 'label' | 'truck' | 'forklift';

export function Icon({ name, size = 20, className = '' }: { name: IconName; size?: number; className?: string }) {
  const props = { width: size, height: size, viewBox: '0 0 24 24', xmlns: 'http://www.w3.org/2000/svg', className: `icon ${className}` } as any;
  switch (name) {
    case 'home':
      return (
        <svg {...props} fill="currentColor"><path d="M12 3 3 10v10h6v-6h6v6h6V10l-9-7z"/></svg>
      );
    case 'products':
      return (
        <svg {...props} fill="currentColor"><path d="M3 7l9-4 9 4-9 4-9-4zm0 5l9 4 9-4v7H3v-7z"/></svg>
      );
    case 'suppliers':
      return (
        <svg {...props} fill="currentColor"><path d="M4 6h16v4H4zM4 12h10v6H4zM16 12h4v6h-4z"/></svg>
      );
    case 'customers':
      return (
        <svg {...props} fill="currentColor"><path d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4zm-8 8a8 8 0 1 1 16 0z"/></svg>
      );
    case 'purchases':
      return (
        <svg {...props} fill="currentColor"><path d="M7 6h14l-1 12H8z"/><path d="M3 6h3l2 12H5z"/></svg>
      );
    case 'sales':
      return (
        <svg {...props} fill="currentColor"><path d="M4 4h16v4H4zM4 10h10v4H4zM4 16h16v4H4z"/></svg>
      );
    case 'inventory':
      return (
        <svg {...props} fill="currentColor"><path d="M4 8l8-4 8 4v10l-8 4-8-4z"/></svg>
      );
    case 'receptions':
      return (
        <svg {...props} fill="currentColor"><path d="M3 4h6v6H3zM9 10h6v6H9zM15 4h6v6h-6zM3 16h6v4H3zM15 16h6v4h-6z"/></svg>
      );
    case 'orders':
      return (
        <svg {...props} fill="currentColor"><path d="M6 3h12v4H6zM4 9h16v12H4z"/></svg>
      );
    case 'reports':
      return (
        <svg {...props} fill="currentColor"><path d="M5 3h14v18H5z"/><path d="M8 7h8v2H8zM8 11h8v2H8zM8 15h8v2H8z"/></svg>
      );
    case 'locations':
      return (
        <svg {...props} fill="currentColor"><path d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 9a2 2 0 1 1 2-2 2 2 0 0 1-2 2z"/></svg>
      );
    case 'label':
      return (
        <svg {...props} fill="currentColor"><path d="M3 7v10l9 4 9-4V7l-9-4z"/></svg>
      );
    case 'truck':
      return (
        <svg {...props} fill="currentColor"><path d="M2 6h11v8H2zM13 9h4l3 3v2h-7z"/><circle cx="6" cy="16" r="2"/><circle cx="17" cy="16" r="2"/></svg>
      );
    case 'forklift':
      return (
        <svg {...props} fill="currentColor"><path d="M4 14h6l-2-7H6zM13 7h3v9h-3z"/><circle cx="7" cy="17" r="2"/><circle cx="15" cy="17" r="2"/></svg>
      );
    default:
      return <svg {...props} />;
  }
}

export function IconTile({ children, size = 28, className = '' }: { children: React.ReactNode; size?: number; className?: string }) {
  return (
    <span className={`icon-tile ${className}`} style={{ width: size, height: size }}>
      {children}
    </span>
  );
}

