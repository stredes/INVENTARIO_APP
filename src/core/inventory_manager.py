from __future__ import annotations
from dataclasses import dataclass
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
    """Errores de inventario."""


@dataclass(frozen=True)
class MovementResult:
    product_id: int
    old_stock: int
    new_stock: int
    qty: int
    movement: str  # "entry" | "exit"


class InventoryManager:
    """
    Alta/baja de stock y registro de movimientos.
    """

    def __init__(self, session: Optional[Session] = None) -> None:
        self.session: Session = session or get_session()
        self.products = ProductRepository(self.session)
        self.entries = StockEntryRepository(self.session)
        self.exits = StockExitRepository(self.session)

    # ---------------------------
    # Helpers
    # ---------------------------
    def _get_product(self, product_id: int) -> Product:
        p = self.products.get(product_id)
        if not p:
            raise InventoryError(f"Producto id={product_id} no existe")
        return p

    # ---------------------------
    # API
    # ---------------------------
    def register_entry(
        self,
        *,
        product_id: int,
        cantidad: int,
        motivo: Optional[str] = None,
        when: Optional[datetime] = None,
    ) -> MovementResult:
        """
        Suma stock y registra en stock_entries.
        `when` se guarda en el campo `fecha` (NO existe `fecha_entrada`).
        """
        if cantidad <= 0:
            raise InventoryError("La cantidad de entrada debe ser > 0")

        p = self._get_product(product_id)
        old = int(p.stock_actual or 0)
        new = old + int(cantidad)

        entry = StockEntry(
            id_producto=p.id,
            cantidad=int(cantidad),
            motivo=motivo,
            fecha=when or datetime.utcnow(),  # <--- campo correcto
        )
        self.entries.add(entry)

        p.stock_actual = new
        self.session.flush()
        return MovementResult(product_id=p.id, old_stock=old, new_stock=new, qty=int(cantidad), movement="entry")

    def register_exit(
        self,
        *,
        product_id: int,
        cantidad: int,
        motivo: Optional[str] = None,
        when: Optional[datetime] = None,
    ) -> MovementResult:
        """
        Resta stock y registra en stock_exits.
        `when` se guarda en el campo `fecha`.
        """
        if cantidad <= 0:
            raise InventoryError("La cantidad de salida debe ser > 0")

        p = self._get_product(product_id)
        old = int(p.stock_actual or 0)
        if cantidad > old:
            raise InventoryError(
                f"Stock insuficiente para producto id={product_id}. Stock={old}, solicitado={cantidad}"
            )
        new = old - int(cantidad)

        exit_ = StockExit(
            id_producto=p.id,
            cantidad=int(cantidad),
            motivo=motivo,
            fecha=when or datetime.utcnow(),  # <--- campo correcto
        )
        self.exits.add(exit_)

        p.stock_actual = new
        self.session.flush()
        return MovementResult(product_id=p.id, old_stock=old, new_stock=new, qty=int(cantidad), movement="exit")
