from __future__ import annotations

from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from src.core import PurchaseItem, PurchaseManager, SaleItem, SalesManager
from src.data import database as inventory_db
from src.data.models import Customer, Product, Purchase, Reception, Sale, StockEntry, StockExit, Supplier

from tests.test_reception_cycle import apply_reception


def seed_full_cycle_entities(session):
    supplier = Supplier(
        razon_social="Proveedor Ciclo Completo SPA",
        rut="76.555.100-1",
        contacto="Operaciones",
        email="operaciones@ciclo.cl",
    )
    customer = Customer(
        razon_social="Cliente Ciclo Completo SPA",
        rut="96.444.200-2",
        contacto="Finanzas",
        email="finanzas@cliente.cl",
    )
    session.add_all([supplier, customer])
    session.flush()

    p1 = Product(
        nombre="Producto Ciclo A",
        sku="CYCLE-A",
        precio_compra=100.0,
        precio_venta=175.0,
        stock_actual=0,
        unidad_medida="unidad",
        id_proveedor=supplier.id,
    )
    p2 = Product(
        nombre="Producto Ciclo B",
        sku="CYCLE-B",
        precio_compra=50.0,
        precio_venta=90.0,
        stock_actual=0,
        unidad_medida="unidad",
        id_proveedor=supplier.id,
    )
    session.add_all([p1, p2])
    session.commit()
    session.refresh(supplier)
    session.refresh(customer)
    session.refresh(p1)
    session.refresh(p2)
    return supplier, customer, p1, p2


def _load_facturion_connection_module():
    project_root = Path(__file__).resolve().parents[1]
    fact_root = project_root / "facturion-main" / "facturion-main"
    module_path = fact_root / "database" / "connection.py"

    import sys

    if str(fact_root) not in sys.path:
        sys.path.insert(0, str(fact_root))

    spec = spec_from_file_location("facturion_connection_test", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("No se pudo cargar database.connection de Facturion.")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_system_cycle_supports_end_to_end_closure(session):
    supplier, customer, p1, p2 = seed_full_cycle_entities(session)
    purchases = PurchaseManager(session)
    sales = SalesManager(session)

    purchase = purchases.create_purchase(
        supplier_id=supplier.id,
        items=[
            PurchaseItem(product_id=p1.id, cantidad=10, precio_unitario=Decimal("100.00")),
            PurchaseItem(product_id=p2.id, cantidad=5, precio_unitario=Decimal("50.00")),
        ],
        estado="Pendiente",
        apply_to_stock=False,
    )

    session.refresh(p1)
    session.refresh(p2)
    assert str(purchase.estado).lower() == "pendiente"
    assert p1.stock_actual == 0
    assert p2.stock_actual == 0

    partial_reception = apply_reception(
        session,
        purchase.id,
        items=[{"product_id": p1.id, "qty": 4}],
        tipo_doc="Factura",
        apply_to_stock=True,
    )
    session.refresh(purchase)
    session.refresh(p1)
    session.refresh(p2)
    assert str(purchase.estado).lower() == "incompleta"
    assert p1.stock_actual == 4
    assert p2.stock_actual == 0

    final_reception = apply_reception(
        session,
        purchase.id,
        items=[
            {"product_id": p1.id, "qty": 6},
            {"product_id": p2.id, "qty": 5},
        ],
        tipo_doc="Factura",
        apply_to_stock=True,
    )
    session.refresh(purchase)
    session.refresh(p1)
    session.refresh(p2)
    assert str(purchase.estado).lower() == "completada"
    assert p1.stock_actual == 10
    assert p2.stock_actual == 5
    reception_ids = [partial_reception.id, final_reception.id]

    sale = sales.create_sale(
        customer_id=customer.id,
        items=[
            SaleItem(product_id=p1.id, cantidad=3, precio_unitario=Decimal("175.00")),
            SaleItem(product_id=p2.id, cantidad=2, precio_unitario=Decimal("90.00")),
        ],
        estado="Confirmada",
        apply_to_stock=True,
    )
    session.refresh(p1)
    session.refresh(p2)
    assert str(sale.estado).lower() == "confirmada"
    assert p1.stock_actual == 7
    assert p2.stock_actual == 3
    assert session.query(StockExit).filter(StockExit.id_producto.in_([p1.id, p2.id])).count() == 2

    sales.cancel_sale(sale.id, revert_stock=True)
    session.refresh(p1)
    session.refresh(p2)
    session.refresh(sale)
    assert str(sale.estado).lower() == "cancelada"
    assert p1.stock_actual == 10
    assert p2.stock_actual == 5

    purchases.delete_purchase(purchase.id, revert_stock=True)
    session.refresh(p1)
    session.refresh(p2)
    assert p1.stock_actual == 0
    assert p2.stock_actual == 0
    assert session.get(Purchase, purchase.id) is None
    assert session.get(Sale, sale.id) is not None
    assert session.query(Reception).filter(Reception.id_compra == purchase.id).count() == 0
    assert (
        session.query(StockEntry)
        .filter(StockEntry.id_recepcion.in_(reception_ids))
        .count()
        == 0
    )


def test_facturion_database_is_strictly_isolated_from_inventory_app():
    inventory_engine = inventory_db.get_engine()
    inventory_path = Path(str(inventory_engine.url.database)).resolve()

    fact_connection = _load_facturion_connection_module()
    fact_path = Path(fact_connection.DB_PATH).resolve()

    assert inventory_path != fact_path
    assert inventory_path.name != "facturion.db"
    assert "facturion-main" not in inventory_path.as_posix().lower()
    assert fact_path.name == "facturion.db"
    assert "facturion-main" in fact_path.as_posix().lower()
