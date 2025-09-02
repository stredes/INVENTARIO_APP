"""
InventoryManager
================
Orquesta entradas/salidas de stock y mantiene el campo denormalizado
Product.stock_actual coherente con los movimientos.

Reglas:
- No permite stock negativo.
- Entradas opcionalmente pueden asociarse a una compra (id_compra).
- Todas las operaciones se hacen en transacción (commit/rollback atómico).

Uso típico:
    inv = InventoryManager()
    inv.register_entry(product_id=1, cantidad=10, motivo="Compra", id_compra=5)
    inv.register_exit(product_id=1, cantidad=3, motivo="Venta mostrador")
    stock = inv.get_stock(1)
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.data.database import get_session
from src.data.models import Product, StockEntry, StockExit
from src.data.repository import (
    ProductRepository,
    StockEntryRepository,
    StockExitRepository,
)


class InventoryError(Exception):
    """Errores de inventario (stock, ids inexistentes, etc.)."""


class InventoryManager:
    def __init__(self, session: Optional[Session] = None) -> None:
        # Usamos la sesión global (scoped_session) si no se entrega una explícita
        self.session: Session = (session or get_session())

        # Repos
        self.products = ProductRepository(self.session)
        self.entries = StockEntryRepository(self.session)
        self.exits = StockExitRepository(self.session)

    # -------------------------
    # Consultas
    # -------------------------
    def get_stock(self, product_id: int) -> int:
        """Retorna el stock_actual del producto."""
        prod = self.products.get(product_id)
        if not prod:
            raise InventoryError(f"Producto id={product_id} no existe")
        return int(prod.stock_actual or 0)

    # -------------------------
    # Movimientos
    # -------------------------
    def register_entry(
        self,
        product_id: int,
        cantidad: int,
        motivo: Optional[str] = None,
        id_compra: Optional[int] = None,
        when: Optional[datetime] = None,
    ) -> StockEntry:
        """
        Registra una ENTRADA de stock:
        - Crea StockEntry
        - Suma a Product.stock_actual
        """
        if cantidad <= 0:
            raise InventoryError("La cantidad de entrada debe ser > 0")

        prod = self.products.get(product_id)
        if not prod:
            raise InventoryError(f"Producto id={product_id} no existe")

        when = when or datetime.utcnow()

        try:
            entry = StockEntry(
                id_producto=product_id,
                cantidad=cantidad,
                fecha_entrada=when,
                id_compra=id_compra,
            )
            self.entries.add(entry)

            # Actualizar stock denormalizado
            prod.stock_actual = (prod.stock_actual or 0) + cantidad

            self.session.commit()
            # refrescamos para obtener IDs autoincrement, etc.
            self.session.refresh(entry)
            self.session.refresh(prod)
            return entry
        except Exception:
            self.session.rollback()
            raise

    def register_exit(
        self,
        product_id: int,
        cantidad: int,
        motivo: Optional[str] = None,
        when: Optional[datetime] = None,
    ) -> StockExit:
        """
        Registra una SALIDA de stock:
        - Crea StockExit
        - Resta de Product.stock_actual (no permite negativo)
        """
        if cantidad <= 0:
            raise InventoryError("La cantidad de salida debe ser > 0")

        prod = self.products.get(product_id)
        if not prod:
            raise InventoryError(f"Producto id={product_id} no existe")

        if (prod.stock_actual or 0) < cantidad:
            raise InventoryError(
                f"Stock insuficiente para producto id={product_id}: "
                f"stock_actual={prod.stock_actual}, requerido={cantidad}"
            )

        when = when or datetime.utcnow()

        try:
            exit_ = StockExit(
                id_producto=product_id,
                cantidad=cantidad,
                fecha_salida=when,
                motivo=motivo,
            )
            self.exits.add(exit_)

            # Actualizar stock denormalizado
            prod.stock_actual = (prod.stock_actual or 0) - cantidad

            self.session.commit()
            self.session.refresh(exit_)
            self.session.refresh(prod)
            return exit_
        except Exception:
            self.session.rollback()
            raise
