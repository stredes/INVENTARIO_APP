import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({ status: 'ok', service: 'inventario-app', ts: new Date().toISOString() });
}

