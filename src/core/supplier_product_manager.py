"""
SupplierProductManager
======================
Gestión de la relación Proveedor↔Producto (tabla supplier_products):
- Vincular (upsert) proveedor/producto con precio.
- Actualizar precio/fecha de última compra.
- Consultas de productos por proveedor y proveedores por producto.
"""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.database import get_session
from src.data.models import Product, Supplier, SupplierProduct
from src.data.repository import (
    SupplierProductRepository,
    SupplierRepository,
    ProductRepository,
)


class SupplierProductError(Exception):
    """Errores de relación proveedor-producto."""


class SupplierProductManager:
    def __init__(self, session: Optional[Session] = None) -> None:
        self.session: Session = (session or get_session())

        self.suppliers = SupplierRepository(self.session)
        self.products = ProductRepository(self.session)
        self.links = SupplierProductRepository(self.session)

    # -------------------------
    # Upserts / Updates
    # -------------------------
    def link_or_update(
        self,
        supplier_id: int,
        product_id: int,
        precio: float,
        fecha_ultima_compra: Optional[datetime] = None,
    ) -> SupplierProduct:
        """
        Vincula proveedor↔producto (upsert). Si existe, actualiza precio/fecha.
        """
        if precio <= 0:
            raise SupplierProductError("El precio del proveedor debe ser > 0")

        if not self.suppliers.get(supplier_id):
            raise SupplierProductError(f"Proveedor id={supplier_id} no existe")
        if not self.products.get(product_id):
            raise SupplierProductError(f"Producto id={product_id} no existe")

        try:
            # ¿Existe ya el vínculo?
            stmt = select(SupplierProduct).where(
                SupplierProduct.id_proveedor == supplier_id,
                SupplierProduct.id_producto == product_id,
            )
            existing = self.session.execute(stmt).scalar_one_or_none()

            if existing:
                existing.precio_proveedor = float(precio)
                if fecha_ultima_compra:
                    existing.fecha_ultima_compra = fecha_ultima_compra
                self.session.commit()
                self.session.refresh(existing)
                return existing

            # Si no existe, crear
            sp = SupplierProduct(
                id_proveedor=supplier_id,
                id_producto=product_id,
                precio_proveedor=float(precio),
                fecha_ultima_compra=fecha_ultima_compra,
            )
            self.links.add(sp)
            self.session.commit()
            self.session.refresh(sp)
            return sp

        except Exception:
            self.session.rollback()
            raise

    # -------------------------
    # Consultas
    # -------------------------
    def get_products_for_supplier(self, supplier_id: int) -> List[Tuple[Product, SupplierProduct]]:
        """
        Lista de (Product, SupplierProduct) para un proveedor.
        """
        if not self.suppliers.get(supplier_id):
            raise SupplierProductError(f"Proveedor id={supplier_id} no existe")

        stmt = (
            select(Product, SupplierProduct)
            .join(SupplierProduct, SupplierProduct.id_producto == Product.id)
            .where(SupplierProduct.id_proveedor == supplier_id)
        )
        rows = self.session.execute(stmt).all()
        return [(r[0], r[1]) for r in rows]

    def get_suppliers_for_product(self, product_id: int) -> List[Tuple[Supplier, SupplierProduct]]:
        """
        Lista de (Supplier, SupplierProduct) para un producto.
        """
        if not self.products.get(product_id):
            raise SupplierProductError(f"Producto id={product_id} no existe")

        stmt = (
            select(Supplier, SupplierProduct)
            .join(SupplierProduct, SupplierProduct.id_proveedor == Supplier.id)
            .where(SupplierProduct.id_producto == product_id)
        )
        rows = self.session.execute(stmt).all()
        return [(r[0], r[1]) for r in rows]
