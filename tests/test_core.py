from __future__ import annotations
import pytest

from src.core import (
    InventoryManager,
    InventoryError,
    PurchaseManager,
    PurchaseItem,
    PurchaseError,
)
from src.data.models import Product, Supplier


def seed_basic(session):
    """Crea un producto y un proveedor base."""
    s = Supplier(
        razon_social="Proveedor Salud SPA",
        rut="76.000.000-0",
        contacto="Ventas",
        telefono="+56 2 1234567",
        email="ventas@saludspa.cl",
    )
    session.add(s)
    session.flush()  # obtener s.id para FK

    p = Product(
        nombre="Mascarilla Quirúrgica",
        sku="MQ-001",
        precio_compra=50.0,
        precio_venta=100.0,
        stock_actual=0,
        unidad_medida="unidad",
        id_proveedor=s.id,
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    session.refresh(s)
    return p, s


def test_inventory_entry_exit_updates_stock(session):
    p, _ = seed_basic(session)
    inv = InventoryManager(session)

    # Entrada +10
    entrada = inv.register_entry(product_id=p.id, cantidad=10, motivo="Ajuste inicial")
    assert entrada.new_stock == 10
    session.refresh(p)
    assert p.stock_actual == 10

    # Salida -4
    salida = inv.register_exit(product_id=p.id, cantidad=4, motivo="Consumo interno")
    assert salida.new_stock == 6
    session.refresh(p)
    assert p.stock_actual == 6


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
    session.refresh(p)
    assert p.stock_actual == 25

    # Segunda compra pendiente que NO impacta stock
    purchase2 = pm.create_purchase(
        supplier_id=s.id,
        items=[PurchaseItem(product_id=p.id, cantidad=10, precio_unitario=44.0)],
        estado="Pendiente",
        apply_to_stock=False,
    )
    assert purchase2.id is not None
    session.refresh(p)
    assert p.stock_actual == 25  # sin cambios


def test_purchase_manager_rejects_unknown_supplier(session):
    p, _ = seed_basic(session)
    pm = PurchaseManager(session)

    with pytest.raises(PurchaseError):
        pm.create_purchase(
            supplier_id=999999,
            items=[PurchaseItem(product_id=p.id, cantidad=1, precio_unitario=10)],
        )


def test_purchase_manager_rejects_items_with_wrong_supplier(session):
    p, s1 = seed_basic(session)
    pm = PurchaseManager(session)

    s2 = Supplier(
        razon_social="Proveedor Secundario",
        rut="76.111.222-3",
        contacto="QA",
        email="qa@secundario.cl",
    )
    session.add(s2)
    session.commit()

    with pytest.raises(PurchaseError) as excinfo:
        pm.create_purchase(
            supplier_id=s2.id,
            items=[PurchaseItem(product_id=p.id, cantidad=1, precio_unitario=10)],
        )
    assert "no corresponde al proveedor" in str(excinfo.value)


def test_purchase_manager_validates_item_quantities(session):
    p, s = seed_basic(session)
    pm = PurchaseManager(session)

    with pytest.raises(PurchaseError):
        pm.create_purchase(
            supplier_id=s.id,
            items=[PurchaseItem(product_id=p.id, cantidad=0, precio_unitario=10)],
        )
