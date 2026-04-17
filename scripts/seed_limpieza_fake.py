"""
Seed de datos fake para articulos de limpieza.

Inserta o actualiza:
- 1 proveedor de limpieza
- un catalogo base de productos de aseo / limpieza

Uso:
  python -m scripts.seed_limpieza_fake
  python -m scripts.seed_limpieza_fake --sum-stock
  python -m scripts.seed_limpieza_fake --cleanup
  python -m scripts.seed_limpieza_fake --margen 35
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.database import get_session  # type: ignore
from src.data.models import Product, Supplier  # type: ignore
from src.data.repository import ProductRepository  # type: ignore
from src.utils.money import D, q2  # type: ignore


@dataclass
class Item:
    sku: str
    nombre: str
    unidad: str
    precio_neto: float
    stock_inicial: int
    familia: str = "Limpieza"


SUPPLIER = {
    "name": "Limpieza Integral SpA",
    "rut": "FAKE-LIMP-76000001",
    "contacto": "Ventas Limpieza",
    "telefono": "+56 9 5555 1111",
    "email": "ventas@limpiezaintegral.fake",
    "direccion": "Av. Aseo 1234, Santiago",
}


ITEMS: List[Item] = [
    Item("LIMP-001", "Cloro gel 900 ml", "900 ml", 1290, 24),
    Item("LIMP-002", "Detergente liquido 3 lt", "3 lt", 3990, 18),
    Item("LIMP-003", "Desinfectante ambiental 5 lt", "5 lt", 4590, 10),
    Item("LIMP-004", "Jabon liquido manos 1 lt", "1 lt", 2790, 16),
    Item("LIMP-005", "Lavalozas limon 750 ml", "750 ml", 1190, 20),
    Item("LIMP-006", "Limpiavidrios gatillo 500 ml", "500 ml", 1690, 14),
    Item("LIMP-007", "Multiuso desengrasante 900 ml", "900 ml", 1890, 15),
    Item("LIMP-008", "Papel higienico 4 rollos", "pack x 4", 1490, 30),
    Item("LIMP-009", "Toalla de papel doble hoja", "pack x 2", 2090, 18),
    Item("LIMP-010", "Bolsa de basura 70x90 x10", "pack x 10", 1490, 22),
    Item("LIMP-011", "Esponja abrasiva x3", "pack x 3", 990, 25),
    Item("LIMP-012", "Guantes de aseo talla M", "par", 1590, 12),
    Item("LIMP-013", "Mopa de microfibra", "unidad", 4290, 8),
    Item("LIMP-014", "Escoba multiuso", "unidad", 3590, 9),
    Item("LIMP-015", "Pala plastica con mango", "unidad", 2490, 7),
    Item("LIMP-016", "Amonio cuaternario 5 lt", "5 lt", 6990, 6),
    Item("LIMP-017", "Alcohol gel 1 lt", "1 lt", 3290, 14),
    Item("LIMP-018", "Servilletas 100 unidades", "pack x 100", 890, 28),
]


def ensure_supplier(session, *, name: str, rut: str, contacto: str, telefono: str, email: str, direccion: str) -> Supplier:
    supplier = session.query(Supplier).filter(Supplier.rut == rut).first()
    if supplier is None:
        supplier = Supplier(
            razon_social=name,
            rut=rut,
            contacto=contacto,
            telefono=telefono,
            email=email,
            direccion=direccion,
        )
        session.add(supplier)
        session.flush()
    else:
        supplier.razon_social = name
        supplier.contacto = contacto or supplier.contacto
        supplier.telefono = telefono or supplier.telefono
        supplier.email = email or supplier.email
        supplier.direccion = direccion or supplier.direccion
        session.flush()
    return supplier


def cleanup_products_of_supplier(session, supplier_id: int) -> None:
    repo = ProductRepository(session)
    removed, kept = 0, 0
    for product in session.query(Product).filter(Product.id_proveedor == supplier_id).all():
        try:
            repo.delete(int(product.id))
            removed += 1
        except Exception:
            kept += 1
    session.commit()
    print(f"Limpieza proveedor -> eliminados: {removed}, con dependencias: {kept}")


def upsert_products(session, supplier: Supplier, items: List[Item], *, margen_pct: float = 30.0) -> List[Product]:
    created: List[Product] = []
    iva = D("0.19")
    margin = D(margen_pct) / D(100)

    for item in items:
        precio_compra = q2(D(item.precio_neto))
        precio_venta = q2((precio_compra * (D(1) + iva)) * (D(1) + margin))
        product: Optional[Product] = session.query(Product).filter(Product.sku == item.sku).first()
        if product is None:
            product = Product(
                sku=item.sku,
                nombre=item.nombre,
                precio_compra=precio_compra,
                precio_venta=precio_venta,
                stock_actual=0,
                unidad_medida=item.unidad,
                familia=item.familia,
                id_proveedor=int(supplier.id),
            )
            session.add(product)
        else:
            product.nombre = item.nombre
            product.precio_compra = precio_compra
            product.precio_venta = precio_venta
            product.unidad_medida = item.unidad
            product.familia = item.familia
            product.id_proveedor = int(supplier.id)
        created.append(product)

    session.commit()
    return created


def sum_stock(session, items: List[Item]) -> None:
    for item in items:
        product = session.query(Product).filter(Product.sku == item.sku).first()
        if not product:
            continue
        product.stock_actual = int((product.stock_actual or 0) + int(item.stock_inicial or 0))
    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed fake de articulos de limpieza")
    parser.add_argument("--cleanup", action="store_true", help="Elimina productos del proveedor si no tienen dependencias")
    parser.add_argument("--sum-stock", action="store_true", help="Suma stock inicial a los productos seed")
    parser.add_argument("--margen", type=float, default=30.0, help="Margen para calcular precio_venta")
    args = parser.parse_args()

    session = get_session()
    try:
        supplier = ensure_supplier(session, **SUPPLIER)
        if args.cleanup:
            cleanup_products_of_supplier(session, int(supplier.id))
        products = upsert_products(session, supplier, ITEMS, margen_pct=args.margen)
        if args.sum_stock:
            sum_stock(session, ITEMS)

        print(f"Proveedor listo: {supplier.razon_social} ({supplier.rut})")
        print(f"Productos preparados: {len(products)}")
        if args.sum_stock:
            print("Stock inicial sumado a los productos.")
        print("Seed de limpieza finalizado.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
