from __future__ import annotations

from decimal import Decimal

import pytest

from src.core import PurchaseItem, PurchaseManager, SaleItem, SalesManager
from src.core.inventory_manager import InventoryError
from src.data.models import Customer, Product, Purchase, Sale, StockEntry, StockExit, Supplier


def seed_flow_entities(session):
    supplier = Supplier(
        razon_social="Proveedor Flujo SPA",
        rut="79.300.000-0",
        contacto="Bodega",
        email="bodega@flujo.cl",
    )
    customer = Customer(
        razon_social="Cliente Flujo SPA",
        rut="22.222.222-2",
        contacto="Caja",
        email="caja@flujo.cl",
    )
    session.add_all([supplier, customer])
    session.flush()

    product = Product(
        nombre="Producto Flujo",
        sku="FLOW-001",
        precio_compra=100.0,
        precio_venta=180.0,
        stock_actual=0,
        unidad_medida="unidad",
        id_proveedor=supplier.id,
    )
    session.add(product)
    session.commit()
    session.refresh(supplier)
    session.refresh(customer)
    session.refresh(product)
    return supplier, customer, product


def test_factura_purchase_then_paid_sale_closes_stock_cycle(session):
    supplier, customer, product = seed_flow_entities(session)
    purchases = PurchaseManager(session)
    sales = SalesManager(session)

    purchase = purchases.create_purchase(
        supplier_id=supplier.id,
        items=[PurchaseItem(product_id=product.id, cantidad=10, precio_unitario=Decimal("100.00"))],
        estado="Completada",
        apply_to_stock=True,
    )
    sale = sales.create_sale(
        customer_id=customer.id,
        items=[SaleItem(product_id=product.id, cantidad=4, precio_unitario=Decimal("180.00"))],
        estado="Pagada",
        apply_to_stock=True,
    )

    session.refresh(product)
    assert session.get(Purchase, purchase.id) is not None
    assert session.get(Sale, sale.id) is not None
    assert str(purchase.estado).lower() == "completada"
    assert str(sale.estado).lower() == "pagada"
    assert product.stock_actual == 6

    entries = session.query(StockEntry).filter(StockEntry.id_producto == product.id).all()
    exits = session.query(StockExit).filter(StockExit.id_producto == product.id).all()
    assert len(entries) == 1
    assert len(exits) == 1
    assert entries[0].cantidad == 10
    assert exits[0].cantidad == 4


def test_order_purchase_does_not_feed_inventory_until_real_entry_exists(session):
    supplier, customer, product = seed_flow_entities(session)
    purchases = PurchaseManager(session)
    sales = SalesManager(session)

    order_purchase = purchases.create_purchase(
        supplier_id=supplier.id,
        items=[PurchaseItem(product_id=product.id, cantidad=5, precio_unitario=Decimal("100.00"))],
        estado="Pendiente",
        apply_to_stock=False,
    )

    session.refresh(product)
    assert str(order_purchase.estado).lower() == "pendiente"
    assert product.stock_actual == 0

    with pytest.raises(InventoryError):
        sales.create_sale(
            customer_id=customer.id,
            items=[SaleItem(product_id=product.id, cantidad=1, precio_unitario=Decimal("180.00"))],
            estado="Pagada",
            apply_to_stock=True,
        )

    factura_purchase = purchases.create_purchase(
        supplier_id=supplier.id,
        items=[PurchaseItem(product_id=product.id, cantidad=3, precio_unitario=Decimal("100.00"))],
        estado="Completada",
        apply_to_stock=True,
    )
    sale = sales.create_sale(
        customer_id=customer.id,
        items=[SaleItem(product_id=product.id, cantidad=2, precio_unitario=Decimal("180.00"))],
        estado="Confirmada",
        apply_to_stock=True,
    )

    session.refresh(product)
    assert str(factura_purchase.estado).lower() == "completada"
    assert str(sale.estado).lower() == "confirmada"
    assert product.stock_actual == 1


def test_canceling_purchase_and_sale_reopens_stock_consistently(session):
    supplier, customer, product = seed_flow_entities(session)
    purchases = PurchaseManager(session)
    sales = SalesManager(session)

    purchase = purchases.create_purchase(
        supplier_id=supplier.id,
        items=[PurchaseItem(product_id=product.id, cantidad=8, precio_unitario=Decimal("100.00"))],
        estado="Completada",
        apply_to_stock=True,
    )
    sale = sales.create_sale(
        customer_id=customer.id,
        items=[SaleItem(product_id=product.id, cantidad=3, precio_unitario=Decimal("180.00"))],
        estado="Pagada",
        apply_to_stock=True,
    )

    purchases.cancel_purchase(purchase.id, revert_stock=False)
    session.refresh(product)
    assert product.stock_actual == 5

    sales.cancel_sale(sale.id, revert_stock=True)
    session.refresh(product)
    assert product.stock_actual == 8
