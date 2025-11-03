# Despliegue en Vercel (Frontend Web)

Este directorio contiene una landing y un esqueleto de **Next.js** para llevar Inventario App a la web en Vercel.

Limitaciones: la app original usa **Tkinter (GUI de escritorio)** y **SQLite local**, lo cual no es ejecutable en Vercel. Aquí tienes una base para:
- Publicar una landing web.
- Construir un frontend web real y endpoints (API) que se conecten a una base de datos gestionada (PostgreSQL).

## Contenido
- `app/page.tsx`: Landing básica.
- `app/api/health/route.ts`: Endpoint de salud (`/api/health`).
- `app/api/products/route.ts`: Endpoint de ejemplo con datos mock.\n- `app/products/page.tsx`: Listado que consume la API Python (configurable con `NEXT_PUBLIC_API_BASE_URL`).
- `package.json`, `tsconfig.json`, `next.config.mjs`: Configuración Next.js 14 + TypeScript.

## Requisitos
- Node.js 18+ (Vercel/Next requiere Node LTS reciente)
- Una cuenta de Vercel (para desplegar)

## Uso local
```bash
cd vercel
npm install
npm run dev
# Abre http://localhost:3000
```

## Despliegue en Vercel
1) Autenticación e importación del proyecto:
```bash
npm i -g vercel
vercel
```
Sigue el asistente: selecciona el directorio `vercel/` como raíz del proyecto.

2) Variables de entorno (si usas BD gestionada):
- Configura `DATABASE_URL` en la UI de Vercel (Project Settings → Environment Variables).
- Usa un proveedor como Neon/Supabase para PostgreSQL.

3) Producción:
```bash
vercel --prod
```

## Conectar con una Base de Datos
Para pasar de mock a datos reales:
- Opción A (recomendada): expón una **API Python (FastAPI)** fuera de Vercel (Render/Railway/Fly) que reutilice tu lógica/ORM actual (`src/data/*`) apuntando a PostgreSQL, y desde Next.js consume esa API.
- Opción B: crea **routes** serverless en Next.js que consulten directamente la DB (con un pooler serverless y un driver compatible, p.ej. `pg` para Node). No reutiliza el ORM Python.

Ejemplo mínimo (Opción B, Node):
```ts
// app/api/products/route.ts (esbozo)
import { NextResponse } from 'next/server';
import { Pool } from 'pg'

const pool = new Pool({ connectionString: process.env.DATABASE_URL })
export async function GET() {
  const { rows } = await pool.query('SELECT id, name as nombre, sku, stock, sale_price as precio FROM products LIMIT 50')
  return NextResponse.json({ items: rows })
}
```

## Siguientes pasos sugeridos
- Páginas: productos, proveedores, clientes, compras, ventas.
- Autenticación (si es multiusuario), control de roles.
- Migración de SQLite a PostgreSQL (si aún no lo hiciste) y pruebas de compatibilidad.

## Notas
- No se elimina ni modifica tu app de escritorio. Este es un camino paralelo web.
- Si prefieres solo una **página de descargas**, puedes mantener esta landing y enlazar a instaladores (.exe/.dmg/.AppImage) publicados en GitHub Releases.

```
Estructura
vercel/
  app/
    api/
      health/route.ts
      products/route.ts
    layout.tsx
    page.tsx
  package.json
  next.config.mjs
  tsconfig.json
  README.md
```

Páginas añadidas (frontend web):
- `app/products/page.tsx` — listado de productos (usa API Python)
- `app/suppliers/page.tsx` — listado de proveedores
- `app/customers/page.tsx` — listado de clientes
- `app/purchases/page.tsx` — listado de compras + enlace a PDF
- `app/sales/page.tsx` — listado de ventas + enlace a PDF

