from __future__ import annotations
import pytest
from sqlalchemy import select

from src.data.models import Product, Supplier, SupplierProduct
from src.data.repository import (
    ProductRepository,
    SupplierRepository,
    SupplierProductRepository,
)


def test_product_crud_via_repo(session):
    repo = ProductRepository(session)

    supplier = Supplier(
        razon_social="Central Insumos Ltda.",
        rut="76.123.456-7",
        contacto="María",
    )
    session.add(supplier)
    session.flush()

    # Crear
    p = Product(
        nombre="Guantes Nitrilo",
        sku="GN-001",
        precio_compra=1000.0,
        precio_venta=1500.0,
        stock_actual=0,
        unidad_medida="unidad",
        id_proveedor=supplier.id,
    )
    session.add(p)
    session.commit()
    assert p.id is not None

    # Leer por SKU
    got = repo.get_by_sku("GN-001")
    assert got is not None
    assert got.nombre == "Guantes Nitrilo"

    # Listado básico
    items = repo.list()
    assert any(x.sku == "GN-001" for x in items)


def test_supplier_and_link_table(session):
    repo_sup = SupplierRepository(session)
    repo_prod = ProductRepository(session)
    repo_link = SupplierProductRepository(session)

    # Proveedor + Producto
    s = Supplier(
        razon_social="Proveedor Central",
        rut="76.987.654-3",
        contacto="Pedro",
    )
    session.add(s)
    session.flush()

    p = Product(
        nombre="Alcohol Gel 1L",
        sku="AG-1000",
        precio_compra=2500.0,
        precio_venta=3990.0,
        stock_actual=0,
        unidad_medida="lt",
        id_proveedor=s.id,
    )
    session.add(p)
    session.commit()

    # Vincular con precio proveedor
    link = repo_link.link_supplier_product(s.id, p.id, precio=2100.0)
    session.commit()
    assert link.id is not None
    assert link.id_proveedor == s.id and link.id_producto == p.id

    # Verificar unicidad (par proveedor-producto)
    # Inserción directa repetida debería fallar por UniqueConstraint.
    with pytest.raises(Exception):
        dup = SupplierProduct(
            id_proveedor=s.id, id_producto=p.id, precio_proveedor=2000.0
        )
        session.add(dup)
        session.commit()
