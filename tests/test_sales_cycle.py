from __future__ import annotations

from decimal import Decimal

import pytest

from src.core import SalesManager, SaleItem, SalesError
from src.core.inventory_manager import InventoryError
from src.data.models import Customer, Product, Supplier, Sale, SaleDetail
from src.utils.money import q2, money_sum


def seed_customer_with_products(session):
    supplier = Supplier(
        razon_social="Proveedor Ventas SPA",
        rut="77.100.000-0",
        contacto="Ventas",
        email="ventas@proveedor.cl",
    )
    customer = Customer(
        razon_social="Cliente Test",
        rut="11.111.111-1",
        contacto="Compras",
        email="cliente@test.cl",
    )
    session.add_all([supplier, customer])
    session.flush()

    p1 = Product(
        nombre="Producto Venta A",
        sku="PV-001",
        precio_compra=20.0,
        precio_venta=50.0,
        stock_actual=10,
        unidad_medida="unidad",
        id_proveedor=supplier.id,
    )
    p2 = Product(
        nombre="Producto Venta B",
        sku="PV-002",
        precio_compra=10.0,
        precio_venta=30.0,
        stock_actual=8,
        unidad_medida="unidad",
        id_proveedor=supplier.id,
    )
    session.add_all([p1, p2])
    session.commit()
    session.refresh(p1)
    session.refresh(p2)
    session.refresh(customer)
    return customer, p1, p2


def test_sale_confirmed_updates_stock_and_totals(session):
    customer, p1, p2 = seed_customer_with_products(session)
    sm = SalesManager(session)

    items = [
        SaleItem(product_id=p1.id, cantidad=2, precio_unitario=Decimal("50.00")),
        SaleItem(product_id=p2.id, cantidad=3, precio_unitario=Decimal("30.00")),
    ]
    sale = sm.create_sale(
        customer_id=customer.id,
        items=items,
        estado="Confirmada",
        apply_to_stock=True,
    )

    expected_total = q2(money_sum([it.subtotal for it in items]))
    assert q2(sale.total_venta) == expected_total

    session.refresh(p1)
    session.refresh(p2)
    assert p1.stock_actual == 8
    assert p2.stock_actual == 5

    details = session.query(SaleDetail).filter(SaleDetail.id_venta == sale.id).all()
    assert len(details) == 2


def test_sale_reserved_does_not_move_stock(session):
    customer, p1, _ = seed_customer_with_products(session)
    sm = SalesManager(session)

    sale = sm.create_sale(
        customer_id=customer.id,
        items=[SaleItem(product_id=p1.id, cantidad=4, precio_unitario=Decimal("50.00"))],
        estado="Reservada",
        apply_to_stock=True,
    )
    session.refresh(p1)
    assert p1.stock_actual == 10
    assert str(sale.estado).lower() == "reservada"


def test_sale_confirmed_without_stock_move(session):
    customer, p1, _ = seed_customer_with_products(session)
    sm = SalesManager(session)

    sm.create_sale(
        customer_id=customer.id,
        items=[SaleItem(product_id=p1.id, cantidad=3, precio_unitario=Decimal("50.00"))],
        estado="Confirmada",
        apply_to_stock=False,
    )
    session.refresh(p1)
    assert p1.stock_actual == 10


def test_cancel_sale_reverts_stock(session):
    customer, p1, _ = seed_customer_with_products(session)
    sm = SalesManager(session)

    sale = sm.create_sale(
        customer_id=customer.id,
        items=[SaleItem(product_id=p1.id, cantidad=5, precio_unitario=Decimal("50.00"))],
        estado="Confirmada",
        apply_to_stock=True,
    )
    session.refresh(p1)
    assert p1.stock_actual == 5

    sm.cancel_sale(sale.id, revert_stock=True)
    session.refresh(p1)
    session.refresh(sale)
    assert p1.stock_actual == 10
    assert str(sale.estado).lower() == "cancelada"


def test_delete_sale_marks_eliminated_and_reverts_stock(session):
    customer, p1, _ = seed_customer_with_products(session)
    sm = SalesManager(session)

    sale = sm.create_sale(
        customer_id=customer.id,
        items=[SaleItem(product_id=p1.id, cantidad=6, precio_unitario=Decimal("50.00"))],
        estado="Confirmada",
        apply_to_stock=True,
    )
    session.refresh(p1)
    assert p1.stock_actual == 4

    sm.delete_sale(sale.id, revert_stock=True)
    session.refresh(p1)
    session.refresh(sale)
    assert p1.stock_actual == 10
    assert str(sale.estado).lower() == "eliminada"
    assert session.get(Sale, sale.id) is not None


def test_sale_insufficient_stock_raises(session):
    customer, p1, _ = seed_customer_with_products(session)
    sm = SalesManager(session)

    with pytest.raises(InventoryError):
        sm.create_sale(
            customer_id=customer.id,
            items=[SaleItem(product_id=p1.id, cantidad=999, precio_unitario=Decimal("50.00"))],
            estado="Confirmada",
            apply_to_stock=True,
        )


def test_sale_requires_items(session):
    customer, _, _ = seed_customer_with_products(session)
    sm = SalesManager(session)

    with pytest.raises(SalesError):
        sm.create_sale(
            customer_id=customer.id,
            items=[],
        )
