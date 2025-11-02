import { NextResponse } from 'next/server';

// Mock temporal: reemplazar por consultas reales a tu API/BD
const mockProducts = [
  { id: 1, nombre: 'Producto A', sku: 'SKU-001', stock: 15, precio: 1000 },
  { id: 2, nombre: 'Producto B', sku: 'SKU-002', stock: 3, precio: 2500 },
  { id: 3, nombre: 'Producto C', sku: 'SKU-003', stock: 0, precio: 1750 },
];

export async function GET() {
  return NextResponse.json({ items: mockProducts });
}

