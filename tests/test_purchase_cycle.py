from __future__ import annotations

from decimal import Decimal

import pytest

from src.core import PurchaseManager, PurchaseItem
from src.core.inventory_manager import InventoryManager
from src.data.models import Product, Supplier, Purchase, PurchaseDetail, Reception, StockEntry
from src.utils.money import q2, money_sum


def seed_supplier_with_products(session):
    supplier = Supplier(
        razon_social="Proveedor Test SPA",
        rut="76.123.000-0",
        contacto="Compras",
        email="compras@test.cl",
    )
    session.add(supplier)
    session.flush()

    p1 = Product(
        nombre="Producto A",
        sku="PA-001",
        precio_compra=100.0,
        precio_venta=150.0,
        stock_actual=0,
        unidad_medida="unidad",
        id_proveedor=supplier.id,
    )
    p2 = Product(
        nombre="Producto B",
        sku="PB-001",
        precio_compra=50.0,
        precio_venta=90.0,
        stock_actual=0,
        unidad_medida="unidad",
        id_proveedor=supplier.id,
    )
    session.add_all([p1, p2])
    session.commit()
    session.refresh(p1)
    session.refresh(p2)
    session.refresh(supplier)
    return supplier, p1, p2


def test_purchase_completed_sets_received_qty_and_stock(session):
    supplier, p1, p2 = seed_supplier_with_products(session)
    pm = PurchaseManager(session)

    items = [
        PurchaseItem(product_id=p1.id, cantidad=2, precio_unitario=Decimal("100.00")),
        PurchaseItem(product_id=p2.id, cantidad=3, precio_unitario=Decimal("50.00")),
    ]
    purchase = pm.create_purchase(
        supplier_id=supplier.id,
        items=items,
        estado="Completada",
        apply_to_stock=True,
    )

    # Total esperado
    expected_total = q2(money_sum([it.subtotal for it in items]))
    assert q2(purchase.total_compra) == expected_total

    # received_qty debe reflejar compra completada
    details = session.query(PurchaseDetail).filter(PurchaseDetail.id_compra == purchase.id).all()
    assert len(details) == 2
    assert all(int(d.received_qty or 0) == int(d.cantidad or 0) for d in details)

    # Stock actualizado por entradas
    session.refresh(p1)
    session.refresh(p2)
    assert p1.stock_actual == 2
    assert p2.stock_actual == 3

    # Stock entries creados (uno por item)
    se_count = session.query(StockEntry).filter(StockEntry.id_producto.in_([p1.id, p2.id])).count()
    assert se_count == 2


def test_purchase_pending_does_not_move_stock_or_received(session):
    supplier, p1, _ = seed_supplier_with_products(session)
    pm = PurchaseManager(session)

    purchase = pm.create_purchase(
        supplier_id=supplier.id,
        items=[PurchaseItem(product_id=p1.id, cantidad=5, precio_unitario=Decimal("10.00"))],
        estado="Pendiente",
        apply_to_stock=False,
    )

    det = session.query(PurchaseDetail).filter(PurchaseDetail.id_compra == purchase.id).first()
    assert det is not None
    assert int(det.received_qty or 0) == 0

    session.refresh(p1)
    assert p1.stock_actual == 0
    assert session.query(StockEntry).count() == 0


def test_cancel_purchase_reverts_stock(session):
    supplier, p1, _ = seed_supplier_with_products(session)
    pm = PurchaseManager(session)

    purchase = pm.create_purchase(
        supplier_id=supplier.id,
        items=[PurchaseItem(product_id=p1.id, cantidad=4, precio_unitario=Decimal("25.00"))],
        estado="Completada",
        apply_to_stock=True,
    )
    session.refresh(p1)
    assert p1.stock_actual == 4

    pm.cancel_purchase(purchase.id, revert_stock=True)
    session.refresh(p1)
    session.refresh(purchase)
    assert p1.stock_actual == 0
    assert str(purchase.estado).lower() == "cancelada"


def test_delete_purchase_reverts_stock_and_removes_records(session):
    supplier, p1, _ = seed_supplier_with_products(session)
    pm = PurchaseManager(session)

    purchase = pm.create_purchase(
        supplier_id=supplier.id,
        items=[PurchaseItem(product_id=p1.id, cantidad=6, precio_unitario=Decimal("20.00"))],
        estado="Completada",
        apply_to_stock=True,
    )
    session.refresh(p1)
    assert p1.stock_actual == 6

    pm.delete_purchase(purchase.id, revert_stock=True)
    session.refresh(p1)
    assert p1.stock_actual == 0

    assert session.get(Purchase, purchase.id) is None
    dets = session.query(PurchaseDetail).filter(PurchaseDetail.id_compra == purchase.id).all()
    assert dets == []


def test_delete_purchase_cleans_receptions_and_entries(session):
    supplier, p1, _ = seed_supplier_with_products(session)
    pm = PurchaseManager(session)
    inv = InventoryManager(session)

    purchase = pm.create_purchase(
        supplier_id=supplier.id,
        items=[PurchaseItem(product_id=p1.id, cantidad=5, precio_unitario=Decimal("10.00"))],
        estado="Completada",
        apply_to_stock=False,
    )
    session.refresh(p1)
    assert p1.stock_actual == 0

    # Crear recepción + entrada de stock asociada
    rec = Reception(id_compra=purchase.id, tipo_doc="Factura", numero_documento="F-001")
    session.add(rec)
    session.flush()
    rec_id = int(rec.id)
    inv.register_entry(
        product_id=p1.id,
        cantidad=5,
        motivo=f"Recepción {purchase.id}",
        reception_id=rec.id,
    )
    session.commit()
    session.refresh(p1)
    assert p1.stock_actual == 5

    pm.delete_purchase(purchase.id, revert_stock=True)
    session.refresh(p1)
    assert p1.stock_actual == 0

    assert session.query(Reception).filter(Reception.id_compra == purchase.id).count() == 0
    assert session.query(StockEntry).filter(StockEntry.id_recepcion == rec_id).count() == 0
