from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from src.data.database import get_session
from src.data.models import Customer, Product, Sale, SaleDetail
from src.data.repository import (
    CustomerRepository, ProductRepository, SaleRepository, SaleDetailRepository
)
from .inventory_manager import InventoryManager


class SalesError(Exception):
    pass


@dataclass(frozen=True)
class SaleItem:
    product_id: int
    cantidad: int
    precio_unitario: float

    @property
    def subtotal(self) -> float:
        return float(self.cantidad) * float(self.precio_unitario)


class SalesManager:
    def __init__(self, session: Optional[Session] = None) -> None:
        self.session: Session = (session or get_session())
        self.customers = CustomerRepository(self.session)
        self.products = ProductRepository(self.session)
        self.sales = SaleRepository(self.session)
        self.sale_details = SaleDetailRepository(self.session)
        self.inventory = InventoryManager(self.session)

    # ... tu create_sale(...) existente ...

    def cancel_sale(self, sale_id: int, *, revert_stock: bool = True) -> None:
        """
        Cambia estado a 'Cancelada'. Si revert_stock=True y estaba Confirmada,
        reingresa stock (entradas).
        """
        sale = self.sales.get(sale_id)
        if not sale:
            raise SalesError(f"Venta id={sale_id} no existe")

        if sale.estado.lower() == "cancelada":
            return

        if revert_stock and sale.estado.lower() == "confirmada":
            for det in sale.details:
                self.inventory.register_entry(
                    product_id=det.id_producto,
                    cantidad=det.cantidad,
                    motivo=f"Reversa venta {sale_id}",
                    when=datetime.utcnow(),
                )
        sale.estado = "Cancelada"
        self.session.commit()

    def delete_sale(self, sale_id: int, *, revert_stock: bool = True) -> None:
        """
        Elimina la venta y sus detalles. Si estaba Confirmada y revert_stock=True,
        reingresa stock antes de borrar.
        """
        sale = self.sales.get(sale_id)
        if not sale:
            return

        if revert_stock and sale.estado.lower() == "confirmada":
            for det in sale.details:
                self.inventory.register_entry(
                    product_id=det.id_producto,
                    cantidad=det.cantidad,
                    motivo=f"Reversa venta {sale_id}",
                    when=datetime.utcnow(),
                )
        self.sales.delete(sale_id)
        self.session.commit()
