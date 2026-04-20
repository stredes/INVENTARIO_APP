from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from src.data.database import get_session
from src.data.models import Customer, Product, Sale, SaleDetail, SaleServiceDetail
from src.data.repository import (
    CustomerRepository,
    ProductRepository,
    SaleRepository,
    SaleDetailRepository,
    SaleServiceDetailRepository,
)
from .inventory_manager import InventoryManager
from src.utils.money import D, mul, money_sum, q2


class SalesError(Exception):
    """Errores de lógica de ventas."""


@dataclass(frozen=True)
class SaleItem:
    """Ítem de venta (precio_unitario = precio de venta)."""
    product_id: int
    cantidad: int
    precio_unitario: Decimal

    @property
    def subtotal(self) -> Decimal:
        return mul(self.cantidad, self.precio_unitario)


@dataclass(frozen=True)
class ManualSaleItem:
    """Item manual para servicios u otros cargos sin stock."""
    descripcion: str
    cantidad: int
    precio_unitario: Decimal
    afecto_iva: bool = True

    @property
    def subtotal(self) -> Decimal:
        return mul(self.cantidad, self.precio_unitario)


class SalesManager:
    """
    Administra la creación, cancelación y eliminación de ventas,
    y su efecto en el inventario.

    Estados soportados:
      - 'Pagado'      -> puede descontar stock
      - 'Pendiente'   -> NO descuenta stock
    """
    _STATES_THAT_EXIT_STOCK = {"pagado", "pagada", "confirmada"}

    def __init__(self, session: Optional[Session] = None) -> None:
        self.session: Session = session or get_session()
        self.customers = CustomerRepository(self.session)
        self.products = ProductRepository(self.session)
        self.sales = SaleRepository(self.session)
        self.sale_details = SaleDetailRepository(self.session)
        self.sale_service_details = SaleServiceDetailRepository(self.session)
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

    def _validate_service_items(self, items: Iterable[ManualSaleItem]) -> List[ManualSaleItem]:
        items = list(items)
        for it in items:
            if not str(it.descripcion or "").strip():
                raise SalesError("La descripcion del servicio es obligatoria")
            if it.cantidad <= 0:
                raise SalesError(f"Cantidad invalida para servicio '{it.descripcion}'")
            if it.precio_unitario <= 0:
                raise SalesError(f"Precio invalido para servicio '{it.descripcion}'")
        return items

    @staticmethod
    def normalize_state(estado: str | None) -> str:
        """Reduce estados antiguos/nuevos a solo Pagado o Pendiente."""
        raw = str(estado or "").strip().lower()
        if raw in {"pagado", "pagada", "confirmada", "confirmado"}:
            return "Pagado"
        return "Pendiente"

    # -----------------------------
    # API pública
    # -----------------------------
    def create_sale(
        self,
        *,
        customer_id: int,
        items: Iterable[SaleItem],
        service_items: Optional[Iterable[ManualSaleItem]] = None,
        fecha: Optional[datetime] = None,
        estado: str = "Pagado",
        apply_to_stock: bool = True,
        numero_documento: Optional[str] = None,
        mes_referencia: Optional[str] = None,
        monto_neto: Optional[Decimal] = None,
        monto_iva: Optional[Decimal] = None,
        fecha_pagado: Optional[datetime] = None,
        nota: Optional[str] = None,
        estado_externo: Optional[str] = None,
        origen: Optional[str] = None,
    ) -> Sale:
        """
        Crea Sale + SaleDetails.
        - Si estado es 'Pagado' y apply_to_stock=True -> registra SALIDAS de stock.
        - 'Pendiente' no afecta stock al crear.
        """
        fecha = fecha or datetime.utcnow()
        estado = self.normalize_state(estado)
        self._validate_customer(customer_id)
        raw_items = list(items)
        items = self._validate_items(raw_items) if raw_items else []
        service_items = self._validate_service_items(service_items or [])
        if not items and not service_items:
            raise SalesError("La venta debe contener al menos un item")
        total = q2(money_sum([*(it.subtotal for it in items), *(it.subtotal for it in service_items)]))

        try:
            # Cabecera
            sale = Sale(
                id_cliente=customer_id,
                fecha_venta=fecha,
                total_venta=total,
                estado=estado,
                numero_documento=numero_documento,
                mes_referencia=mes_referencia,
                monto_neto=q2(monto_neto) if monto_neto is not None else None,
                monto_iva=q2(monto_iva) if monto_iva is not None else None,
                fecha_pagado=fecha_pagado,
                nota=nota,
                estado_externo=estado_externo,
                origen=origen,
            )
            self.sales.add(sale)
            self.session.flush()  # obtener sale.id

            # Detalle
            for it in items:
                det = SaleDetail(
                    id_venta=sale.id,
                    id_producto=it.product_id,
                    cantidad=it.cantidad,
                    precio_unitario=q2(it.precio_unitario),
                    subtotal=q2(it.subtotal),
                )
                self.sale_details.add(det)

            for it in service_items:
                det = SaleServiceDetail(
                    id_venta=sale.id,
                    descripcion=str(it.descripcion).strip(),
                    cantidad=it.cantidad,
                    precio_unitario=q2(it.precio_unitario),
                    subtotal=q2(it.subtotal),
                    afecto_iva=bool(it.afecto_iva),
                )
                self.sale_service_details.add(det)

            # Stock (si corresponde)
            if estado.lower() in self._STATES_THAT_EXIT_STOCK and apply_to_stock:
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
        Cambia estado a 'Pendiente'.
        Si revert_stock=True y la venta estaba en un estado que **descuenta stock**
        ('Pagado' o estados antiguos equivalentes), reingresa stock (entradas).
        """
        sale = self.sales.get(sale_id)
        if not sale:
            raise SalesError(f"Venta id={sale_id} no existe")

        if sale.estado.lower() == "pendiente":
            return

        if revert_stock and sale.estado.lower() in self._STATES_THAT_EXIT_STOCK:
            for det in sale.details:
                self.inventory.register_entry(
                    product_id=det.id_producto,
                    cantidad=det.cantidad,
                    motivo=f"Reversa venta {sale_id}",
                    when=datetime.utcnow(),
                )
        sale.estado = "Pendiente"
        self.session.commit()

    def delete_sale(self, sale_id: int, *, revert_stock: bool = True) -> None:
        """
        **No borra físicamente**. Marca estado='Pendiente'.
        Si estaba en un estado que **descuenta stock** y revert_stock=True,
        reingresa stock antes de marcar como Pendiente.
        """
        sale = self.sales.get(sale_id)
        if not sale:
            return

        if revert_stock and sale.estado.lower() in self._STATES_THAT_EXIT_STOCK:
            for det in sale.details:
                self.inventory.register_entry(
                    product_id=det.id_producto,
                    cantidad=det.cantidad,
                    motivo=f"Reversa venta {sale_id}",
                    when=datetime.utcnow(),
                )
        sale.estado = "Pendiente"
        self.session.commit()
