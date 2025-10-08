from __future__ import annotations
import pytest

from src.core import (
    InventoryManager, InventoryError,
    PurchaseManager, PurchaseItem,
)
from src.data.models import Product, Supplier


def seed_basic(session):
    """Crea un producto y un proveedor base."""
    p = Product(
        nombre="Mascarilla Quirúrgica",
        sku="MQ-001",
        precio_compra=50.0,
        precio_venta=100.0,
        stock_actual=0,
        unidad_medida="unidad",
    )
    s = Supplier(nombre="Proveedor Salud SPA")
    session.add_all([p, s])
    session.commit()
    session.refresh(p)
    session.refresh(s)
    return p, s


def test_inventory_entry_exit_updates_stock(session):
    p, _ = seed_basic(session)
    inv = InventoryManager(session)

    # Entrada +10
    inv.register_entry(product_id=p.id, cantidad=10, motivo="Ajuste inicial")
    assert inv.get_stock(p.id) == 10

    # Salida -4
    inv.register_exit(product_id=p.id, cantidad=4, motivo="Consumo interno")
    assert inv.get_stock(p.id) == 6


def test_inventory_exit_insufficient_stock_raises(session):
    p, _ = seed_basic(session)
    inv = InventoryManager(session)

    # No hay stock; salida debería fallar
    with pytest.raises(InventoryError):
        inv.register_exit(product_id=p.id, cantidad=1, motivo="Error")


def test_purchase_manager_creates_purchase_and_updates_stock(session):
    p, s = seed_basic(session)
    pm = PurchaseManager(session)

    # Compra completada que impacta stock
    purchase = pm.create_purchase(
        supplier_id=s.id,
        items=[PurchaseItem(product_id=p.id, cantidad=25, precio_unitario=45.0)],
        estado="Completada",
        apply_to_stock=True,
    )
    assert purchase.id is not None

    # Stock actualizado por entradas automáticas
    inv = InventoryManager(session)
    assert inv.get_stock(p.id) == 25

    # Segunda compra pendiente que NO impacta stock
    purchase2 = pm.create_purchase(
        supplier_id=s.id,
        items=[PurchaseItem(product_id=p.id, cantidad=10, precio_unitario=44.0)],
        estado="Pendiente",
        apply_to_stock=False,
    )
    assert purchase2.id is not None
    assert inv.get_stock(p.id) == 25  # sin cambios
