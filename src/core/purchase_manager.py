from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from src.data.database import get_session
from src.data.models import Purchase, PurchaseDetail, Product, Supplier
from src.data.repository import (
    PurchaseRepository,
    PurchaseDetailRepository,
    ProductRepository,
)
from .inventory_manager import InventoryManager


class PurchaseError(Exception):
    """Errores de lógica de compras."""


@dataclass(frozen=True)
class PurchaseItem:
    """
    Ítem de compra para crear Purchase + PurchaseDetails.
    Se usa en la GUI para armar el carrito/detalle antes de confirmar.
    """
    product_id: int
    cantidad: int
    precio_unitario: float

    @property
    def subtotal(self) -> float:
        return float(self.cantidad) * float(self.precio_unitario)


class PurchaseManager:
    """
    Orquesta la creación, cancelación y eliminación de compras,
    y el impacto de movimientos de stock.
    """
    def __init__(self, session: Optional[Session] = None) -> None:
        self.session: Session = session or get_session()
        self.purchases = PurchaseRepository(self.session)
        self.details = PurchaseDetailRepository(self.session)
        self.products = ProductRepository(self.session)
        self.inventory = InventoryManager(self.session)

    # -----------------------------
    # Validaciones internas
    # -----------------------------
    def _validate_supplier(self, supplier_id: int) -> None:
        """
        Verifica que exista el proveedor.
        (Validación simple para no forzar un repositorio de Supplier).
        """
        exists = self.session.query(Supplier.id).filter(Supplier.id == supplier_id).first()
        if not exists:
            raise PurchaseError(f"Proveedor id={supplier_id} no existe")

    def _validate_items(self, items: Iterable[PurchaseItem]) -> List[PurchaseItem]:
        """
        Verifica ítems: cantidad y precio > 0 y que los productos existan.
        """
        items = list(items)
        if not items:
            raise PurchaseError("La compra debe contener al menos un ítem")
        for it in items:
            if it.cantidad <= 0:
                raise PurchaseError(f"Cantidad inválida para product_id={it.product_id}")
            if it.precio_unitario <= 0:
                raise PurchaseError(f"Precio inválido para product_id={it.product_id}")
            prod: Optional[Product] = self.products.get(it.product_id)
            if not prod:
                raise PurchaseError(f"Producto id={it.product_id} no existe")
        return items

    # -----------------------------
    # API pública
    # -----------------------------
    def create_purchase(
        self,
        *,
        supplier_id: int,
        items: Iterable[PurchaseItem],
        fecha: Optional[datetime] = None,
        estado: str = "Completada",   # 'Pendiente' | 'Completada' | 'Cancelada'
        apply_to_stock: bool = True,  # si Completada, suma stock
    ) -> Purchase:
        """
        Crea Purchase + PurchaseDetails. Si estado='Completada' y apply_to_stock=True,
        registra ENTRADAS de stock y actualiza Product.stock_actual.
        """
        fecha = fecha or datetime.utcnow()
        self._validate_supplier(supplier_id)
        items = self._validate_items(items)
        total = sum(it.subtotal for it in items)

        try:
            # Cabecera
            pur = Purchase(
                id_proveedor=supplier_id,
                fecha_compra=fecha,
                total_compra=total,
                estado=estado,
            )
            self.purchases.add(pur)
            self.session.flush()  # para obtener pur.id

            # Detalle
            for it in items:
                det = PurchaseDetail(
                    id_compra=pur.id,
                    id_producto=it.product_id,
                    cantidad=it.cantidad,
                    precio_unitario=it.precio_unitario,
                    subtotal=it.subtotal,
                )
                self.details.add(det)

            # Stock (si corresponde)
            if estado.lower() == "completada" and apply_to_stock:
                for it in items:
                    self.inventory.register_entry(
                        product_id=it.product_id,
                        cantidad=it.cantidad,
                        motivo=f"Compra {pur.id}",
                        when=fecha,
                    )

            self.session.commit()
            self.session.refresh(pur)
            return pur

        except Exception:
            self.session.rollback()
            raise

    def cancel_purchase(self, purchase_id: int, *, revert_stock: bool = True) -> None:
        """
        Cambia estado a 'Cancelada'. Si revert_stock=True y la compra estaba 'Completada',
        genera SALIDAS inversas (resta stock).
        """
        pur = self.purchases.get(purchase_id)
        if not pur:
            raise PurchaseError(f"Compra id={purchase_id} no existe")

        if pur.estado.lower() == "cancelada":
            return

        if revert_stock and pur.estado.lower() == "completada":
            for det in pur.details:
                self.inventory.register_exit(
                    product_id=det.id_producto,
                    cantidad=det.cantidad,
                    motivo=f"Reversa compra {purchase_id}",
                    when=datetime.utcnow(),
                )

        pur.estado = "Cancelada"
        self.session.commit()

    def delete_purchase(self, purchase_id: int, *, revert_stock: bool = True) -> None:
        """
        Elimina la compra y sus detalles. Si estaba 'Completada' y revert_stock=True,
        revierte stock antes de borrar.
        """
        pur = self.purchases.get(purchase_id)
        if not pur:
            # nada que borrar
            return

        if revert_stock and pur.estado.lower() == "completada":
            for det in pur.details:
                self.inventory.register_exit(
                    product_id=det.id_producto,
                    cantidad=det.cantidad,
                    motivo=f"Reversa compra {purchase_id}",
                    when=datetime.utcnow(),
                )

        self.purchases.delete(purchase_id)
        self.session.commit()
