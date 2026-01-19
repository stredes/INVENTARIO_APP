from __future__ import annotations

from decimal import Decimal

import pytest

from src.core import PurchaseManager, PurchaseItem
from src.core.inventory_manager import InventoryManager
from src.data.models import Product, Supplier, PurchaseDetail, Purchase, Reception, StockEntry


def seed_purchase_pending(session):
    supplier = Supplier(
        razon_social="Proveedor Recepcion SPA",
        rut="78.200.000-0",
        contacto="Recepciones",
        email="recepciones@proveedor.cl",
    )
    session.add(supplier)
    session.flush()

    p1 = Product(
        nombre="Producto R1",
        sku="PR-001",
        precio_compra=10.0,
        precio_venta=20.0,
        stock_actual=0,
        unidad_medida="unidad",
        id_proveedor=supplier.id,
    )
    p2 = Product(
        nombre="Producto R2",
        sku="PR-002",
        precio_compra=15.0,
        precio_venta=30.0,
        stock_actual=0,
        unidad_medida="unidad",
        id_proveedor=supplier.id,
    )
    session.add_all([p1, p2])
    session.commit()
    session.refresh(p1)
    session.refresh(p2)
    session.refresh(supplier)

    pm = PurchaseManager(session)
    purchase = pm.create_purchase(
        supplier_id=supplier.id,
        items=[
            PurchaseItem(product_id=p1.id, cantidad=10, precio_unitario=Decimal("10.00")),
            PurchaseItem(product_id=p2.id, cantidad=5, precio_unitario=Decimal("15.00")),
        ],
        estado="Pendiente",
        apply_to_stock=False,
    )
    return purchase, p1, p2


def apply_reception(session, purchase_id: int, items: list[dict], *, tipo_doc: str = "Factura", apply_to_stock: bool = True):
    pur = session.get(Purchase, purchase_id)
    if not pur:
        raise ValueError("Compra no encontrada")

    estado_norm = str(getattr(pur, "estado", "") or "").strip().lower()
    add_stock = bool(apply_to_stock) and estado_norm in ("pendiente", "incompleta")

    rec = Reception(id_compra=pur.id, tipo_doc=tipo_doc, numero_documento="R-1")
    session.add(rec)
    session.flush()

    inv = InventoryManager(session)
    any_received = False

    for it in items:
        prod_id = int(it["product_id"])
        qty = int(it.get("qty", 0) or 0)
        if qty <= 0:
            raise ValueError("Cantidad inválida")
        det = (
            session.query(PurchaseDetail)
            .filter(PurchaseDetail.id_compra == pur.id)
            .filter(PurchaseDetail.id_producto == prod_id)
            .first()
        )
        if not det:
            raise ValueError("Producto no pertenece a la compra")
        remaining = int(det.cantidad or 0) - int(det.received_qty or 0)
        if qty > remaining:
            raise ValueError("Recepción excede lo comprado")

        if add_stock:
            inv.register_entry(
                product_id=prod_id,
                cantidad=qty,
                motivo=f"Recepción OC {pur.id}",
                reception_id=rec.id,
            )
        det.received_qty = int(det.received_qty or 0) + qty
        any_received = True

    if any_received:
        totals = session.query(PurchaseDetail).filter(PurchaseDetail.id_compra == pur.id).all()
        all_received = all(int(d.received_qty or 0) >= int(d.cantidad or 0) for d in totals)
        if all_received:
            td = (tipo_doc or "").lower()
            if td.startswith("fact"):
                pur.estado = "Completada"
            elif td.startswith("gu"):
                pur.estado = "Por pagar"
            else:
                pur.estado = "Por pagar" if add_stock else "Completada"
        else:
            pur.estado = "Incompleta"

    session.commit()
    session.refresh(rec)
    return rec


def test_reception_partial_sets_incompleta_and_stock(session):
    purchase, p1, p2 = seed_purchase_pending(session)

    rec = apply_reception(
        session,
        purchase.id,
        items=[{"product_id": p1.id, "qty": 4}],
        tipo_doc="Factura",
        apply_to_stock=True,
    )

    session.refresh(purchase)
    assert str(purchase.estado).lower() == "incompleta"

    d1 = session.query(PurchaseDetail).filter_by(id_compra=purchase.id, id_producto=p1.id).one()
    d2 = session.query(PurchaseDetail).filter_by(id_compra=purchase.id, id_producto=p2.id).one()
    assert int(d1.received_qty or 0) == 4
    assert int(d2.received_qty or 0) == 0

    session.refresh(p1)
    session.refresh(p2)
    assert p1.stock_actual == 4
    assert p2.stock_actual == 0

    assert session.query(StockEntry).filter(StockEntry.id_recepcion == rec.id).count() == 1


def test_reception_complete_factura_sets_completada(session):
    purchase, p1, _ = seed_purchase_pending(session)

    rec = apply_reception(
        session,
        purchase.id,
        items=[{"product_id": p1.id, "qty": 10}],
        tipo_doc="Factura",
        apply_to_stock=True,
    )

    session.refresh(purchase)
    assert str(purchase.estado).lower() == "completada"

    d1 = session.query(PurchaseDetail).filter_by(id_compra=purchase.id, id_producto=p1.id).one()
    assert int(d1.received_qty or 0) == 10

    session.refresh(p1)
    assert p1.stock_actual == 10
    assert session.query(StockEntry).filter(StockEntry.id_recepcion == rec.id).count() == 1


def test_reception_complete_guia_sets_por_pagar(session):
    purchase, p1, p2 = seed_purchase_pending(session)

    apply_reception(
        session,
        purchase.id,
        items=[
            {"product_id": p1.id, "qty": 10},
            {"product_id": p2.id, "qty": 5},
        ],
        tipo_doc="Guia",
        apply_to_stock=True,
    )

    session.refresh(purchase)
    assert str(purchase.estado).lower() == "por pagar"


def test_reception_exceed_pending_raises(session):
    purchase, p1, _ = seed_purchase_pending(session)

    with pytest.raises(ValueError):
        apply_reception(
            session,
            purchase.id,
            items=[{"product_id": p1.id, "qty": 99}],
            tipo_doc="Factura",
            apply_to_stock=True,
        )
