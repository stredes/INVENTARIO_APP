from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from src.data.database import get_session
from src.data.models import Customer, Product, Sale, SaleDetail
from src.data.repository import (
    CustomerRepository,
    ProductRepository,
    SaleRepository,
    SaleDetailRepository,
)
from .inventory_manager import InventoryManager


class SalesError(Exception):
    """Errores de lógica de ventas."""


@dataclass(frozen=True)
class SaleItem:
    product_id: int
    cantidad: int
    precio_unitario: float

    @property
    def subtotal(self) -> float:
        return float(self.cantidad) * float(self.precio_unitario)


class SalesManager:
    """
    Administra la creación, cancelación y eliminación de ventas,
    y su efecto en el inventario.
    """
    def __init__(self, session: Optional[Session] = None) -> None:
        self.session: Session = session or get_session()
        self.customers = CustomerRepository(self.session)
        self.products = ProductRepository(self.session)
        self.sales = SaleRepository(self.session)
        self.sale_details = SaleDetailRepository(self.session)
        self.inventory = InventoryManager(self.session)

    # -----------------------------
    # Validaciones internas
    # -----------------------------
    def _validate_customer(self, customer_id: int) -> None:
        """Verifica que exista el cliente."""
        exists = self.session.query(Customer.id).filter(Customer.id == customer_id).first()
        if not exists:
            raise SalesError(f"Cliente id={customer_id} no existe")

    def _validate_items(self, items: Iterable[SaleItem]) -> List[SaleItem]:
        """Verifica cantidades, precios y existencia de productos."""
        items = list(items)
        if not items:
            raise SalesError("La venta debe contener al menos un ítem")
        for it in items:
            if it.cantidad <= 0:
                raise SalesError(f"Cantidad inválida para product_id={it.product_id}")
            if it.precio_unitario <= 0:
                raise SalesError(f"Precio inválido para product_id={it.product_id}")
            prod: Optional[Product] = self.products.get(it.product_id)
            if not prod:
                raise SalesError(f"Producto id={it.product_id} no existe")
        return items

    # -----------------------------
    # API pública
    # -----------------------------
    def create_sale(
        self,
        *,
        customer_id: int,
        items: Iterable[SaleItem],
        fecha: Optional[datetime] = None,
        estado: str = "Confirmada",   # 'Borrador' | 'Confirmada' | 'Cancelada'
        apply_to_stock: bool = True,  # si Confirmada, descuenta stock
    ) -> Sale:
        """
        Crea Sale + SaleDetails. Si estado='Confirmada' y apply_to_stock=True,
        registra SALIDAS de stock y actualiza Product.stock_actual.
        """
        fecha = fecha or datetime.utcnow()
        self._validate_customer(customer_id)
        items = self._validate_items(items)
        total = sum(it.subtotal for it in items)

        try:
            # Cabecera
            sale = Sale(
                id_cliente=customer_id,
                fecha_venta=fecha,
                total_venta=total,
                estado=estado,
            )
            self.sales.add(sale)
            self.session.flush()  # obtener sale.id

            # Detalle
            for it in items:
                det = SaleDetail(
                    id_venta=sale.id,
                    id_producto=it.product_id,
                    cantidad=it.cantidad,
                    precio_unitario=it.precio_unitario,
                    subtotal=it.subtotal,
                )
                self.sale_details.add(det)

            # Stock (si corresponde)
            if estado.lower() == "confirmada" and apply_to_stock:
                for it in items:
                    self.inventory.register_exit(
                        product_id=it.product_id,
                        cantidad=it.cantidad,
                        motivo=f"Venta {sale.id}",
                        when=fecha,
                    )

            self.session.commit()
            self.session.refresh(sale)
            return sale

        except Exception:
            self.session.rollback()
            raise

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
