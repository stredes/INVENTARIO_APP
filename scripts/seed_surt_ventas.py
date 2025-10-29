"""
Seed de datos (FAKE) para SURT VENTAS S.A. basado en la orden compartida.

Inserta/actualiza el proveedor y un set de productos representativos con sus
precios NETOS, y opcionalmente crea una compra y suma stock.

Uso:
  # Solo proveedor + productos (upsert por SKU)
  python -m scripts.seed_surt_ventas

  # Además crea una compra en estado Pendiente
  python -m scripts.seed_surt_ventas --create-purchase

  # Además suma stock a los productos con la cantidad de la orden
  python -m scripts.seed_surt_ventas --sum-stock

  # Limpia productos del proveedor sin dependencias antes de insertar
  python -m scripts.seed_surt_ventas --cleanup
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import sys
from pathlib import Path

# Bootstrap sys.path para permitir "from src..." al ejecutar como script
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.database import get_session  # type: ignore
from src.data.models import Supplier, Product, Purchase, PurchaseDetail  # type: ignore
from src.utils.money import D, q2  # type: ignore


@dataclass
class Item:
    sku: str
    nombre: str
    unidad: str
    precio_neto: float
    cantidad: int


# Conjunto de productos (extraídos de la orden)
ITEMS: List[Item] = [
    # Papel higiénico 4 rollos -> tratamos como "bolsa x 4"
    Item("51192",    "PAPEL HIG. 4 ROLLOS 30 MT. H/D CONFORT", "bolsa x 4", 1397, 24),
    # Detergente 3 litros
    Item("434010DF", "DETERGENTE LÍQUIDO 3 LT BIO DESIERTO FL", "lt 3", 4252, 12),
    # Esponja x4
    Item("92057",    "ESPONJA ACANALADA X 4 UN VIRUTEX ANATOM", "caja x 4", 1403, 10),
    # Jabón líquido 750 ml
    Item("41122AV",  "JABÓN LÍQ. 750ML AVENA/ACEITE ALMENDRA", "750 ml", 810, 10),
    # Pasta dental 100 ml
    Item("431012",   "PASTA DENTAL 100 ML COLGATE TRIPLE ACCIÓN", "100 ml", 1121, 12),
    # Lustramuebles aerosol 360 cc ~ 360 ml
    Item("865554",   "LUSTRAMUEBLES A/SOL 360 CC PREMIO LIMÓN", "360 ml", 1184, 12),
    # Insecticida aerosol 360 cc ~ 360 ml
    Item("894865",   "INSECTICIDA A/SOL 360 CC RAID MOSCA Y M", "360 ml", 3297, 2),
    # Toalla papel 2 rollos -> "bolsa x 2"
    Item("40207",    "TOALLA PAPEL 2 ROLL 250 MT M/S RENDIPE", "bolsa x 2", 6224, 5),
]


SUPPLIER = {
    "name": "SURT VENTAS S.A.",
    "rut": "76462580-5",
    "contacto": "Ventas",
    "telefono": "+56 2 8206460",
    "direccion": "Las Hortensias 900, Santiago",
}


def ensure_supplier(session, *, name: str, rut: str, contacto: str, telefono: str, direccion: str) -> Supplier:
    s = session.query(Supplier).filter(Supplier.rut == rut).first()
    if s is None:
        s = Supplier(
            razon_social=name,
            rut=rut,
            contacto=contacto,
            telefono=telefono,
            direccion=direccion,
        )
        session.add(s)
        session.flush()
    else:
        s.razon_social = name
        s.contacto = contacto or s.contacto
        s.telefono = telefono or s.telefono
        s.direccion = direccion or s.direccion
        session.flush()
    return s


def cleanup_products_of_supplier(session, supplier_id: int) -> None:
    from src.data.repository import ProductRepository  # type: ignore

    repo = ProductRepository(session)
    prods = session.query(Product).filter(Product.id_proveedor == supplier_id).all()
    removed, kept = 0, 0
    for p in prods:
        try:
            repo.delete(int(p.id))
            removed += 1
        except Exception:
            kept += 1
    session.commit()
    print(f"Limpieza -> eliminados: {removed}, con dependencias (no removidos): {kept}")


def upsert_products(session, supplier: Supplier, items: List[Item], *, margen_pct: float = 30.0) -> List[Product]:
    out: List[Product] = []
    iva = D("0.19")
    for it in items:
        pc = D(it.precio_neto)
        pmasiva = pc * (D(1) + iva)
        pv = q2(pmasiva * (D(1) + D(margen_pct) / D(100)))
        p: Optional[Product] = session.query(Product).filter(Product.sku == it.sku).first()
        if p is None:
            p = Product(
                sku=it.sku,
                nombre=it.nombre,
                precio_compra=pc,
                precio_venta=pv,
                unidad_medida=it.unidad or "unidad",
                id_proveedor=int(supplier.id),
                stock_actual=0,
            )
            session.add(p)
        else:
            p.nombre = it.nombre
            p.precio_compra = pc
            p.precio_venta = pv
            p.unidad_medida = it.unidad or p.unidad_medida
            p.id_proveedor = int(supplier.id)
        out.append(p)
    session.commit()
    return out


def create_purchase(session, supplier: Supplier, items: List[Item], *, estado: str = "Pendiente") -> Purchase:
    pur = Purchase(
        id_proveedor=int(supplier.id),
        fecha_compra=datetime.now(),
        total_compra=D(0),
        estado=estado,
    )
    session.add(pur)
    session.flush()

    iva = D("1.19")
    total = D(0)
    for it in items:
        prod = session.query(Product).filter(Product.sku == it.sku).first()
        if not prod:
            continue
        qty = int(it.cantidad or 0)
        if qty <= 0:
            continue
        price_bruto = q2(D(it.precio_neto) * iva)
        subtotal = q2(D(qty) * price_bruto)
        det = PurchaseDetail(
            id_compra=int(pur.id),
            id_producto=int(prod.id),
            cantidad=qty,
            precio_unitario=price_bruto,
            subtotal=subtotal,
        )
        session.add(det)
        total += subtotal
    pur.total_compra = q2(total)
    session.commit()
    return pur


def sum_stock(session, items: List[Item]) -> None:
    for it in items:
        prod = session.query(Product).filter(Product.sku == it.sku).first()
        if not prod:
            continue
        prod.stock_actual = int((prod.stock_actual or 0) + int(it.cantidad or 0))
    session.commit()


def main():
    parser = argparse.ArgumentParser(description="Seed FAKE: SURT VENTAS S.A.")
    parser.add_argument("--cleanup", action="store_true", help="Eliminar productos del proveedor sin dependencias")
    parser.add_argument("--create-purchase", action="store_true", help="Crear compra Pendiente con cantidades de la orden")
    parser.add_argument("--sum-stock", action="store_true", help="Incrementar stock con las cantidades de la orden")
    parser.add_argument("--margen", type=float, default=30.0, help="% margen para precio_venta")
    args = parser.parse_args()

    supplier = ensure_supplier(session, **SUPPLIER)
    if args.cleanup:
        cleanup_products_of_supplier(session, int(supplier.id))

    upsert_products(session, supplier, ITEMS, margen_pct=args.margen)

    if args.create_purchase:
        create_purchase(session, supplier, ITEMS, estado="Pendiente")
        print("Compra (Pendiente) creada")
    if args.sum_stock:
        sum_stock(session, ITEMS)
        print("Stock actualizado con cantidades de la orden")

    print("Seed SURT finalizado.")


if __name__ == "__main__":
    session = get_session()
    try:
        main()
    finally:
        session.close()
