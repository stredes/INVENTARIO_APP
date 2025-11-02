from __future__ import annotations

import os
import sys
import pathlib

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from tempfile import NamedTemporaryFile
from io import StringIO
import csv

# Asegura que podamos importar desde src/
ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from src.data.database import get_session, init_db  # noqa: E402
from src.data.repository import (
    ProductRepository,
    SupplierRepository,
    CustomerRepository,
    PurchaseRepository,
    PurchaseDetailRepository,
    SaleRepository,
    SaleDetailRepository,
    LocationRepository,
)
from src.core.inventory_manager import InventoryManager  # noqa: E402
from src.core.purchase_manager import PurchaseManager, PurchaseItem  # noqa: E402
from src.core.sales_manager import SalesManager, SaleItem  # noqa: E402
from .schemas import (
    Message,
    ProductIn,
    ProductOut,
    SupplierIn,
    SupplierOut,
    CustomerIn,
    CustomerOut,
    StockEntryIn,
    StockExitIn,
    PurchaseCreate,
    PurchaseOut,
    SaleCreate,
    SaleOut,
    PurchaseWithDetails,
    SaleWithDetails,
    LocationIn,
    LocationOut,
    SalesReportItem,
    InventoryItemOut,
    ThresholdIn,
    ThresholdOut,
    QuoteCreate,
    ReceptionCreate,
    ReceptionOut,
)


def get_db():
    """Dependency que proporciona una sesión de DB por request.
    Usa scoped_session de src.data.database.
    """
    sess = get_session()
    try:
        yield sess
    finally:
        try:
            sess.remove()  # type: ignore[attr-defined]
        except Exception:
            try:
                sess.close()
            except Exception:
                pass


app = FastAPI(title="Inventario App API", version="0.1.0")

# CORS (ajusta orígenes según tu front)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    # Asegura que la DB esté inicializada
    init_db()


@app.get("/health", response_model=Message)
def health() -> Message:
    return Message(message="ok")


# -----------------------------
# Products
# -----------------------------


@app.get("/products", response_model=list[ProductOut])
def list_products(q: str | None = None, supplier_id: int | None = None, db: Session = Depends(get_db)):
    repo = ProductRepository(db)
    query = repo.query()
    if q:
        qnorm = f"%{q.lower().strip()}%"
        from src.data.models import Product  # local import to avoid circulars

        query = query.filter(
            (Product.nombre.ilike(qnorm)) | (Product.sku.ilike(qnorm))
        )
    if supplier_id is not None:
        from src.data.models import Product

        query = query.filter(Product.id_proveedor == supplier_id)
    return list(query.order_by("id").all())


@app.get("/products/sku/{sku}", response_model=ProductOut)
def get_product_by_sku(sku: str, db: Session = Depends(get_db)):
    repo = ProductRepository(db)
    prod = repo.get_by_sku(sku)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return prod


@app.get("/products/check-sku")
def check_sku(sku: str, db: Session = Depends(get_db)):
    repo = ProductRepository(db)
    return {"exists": repo.exists_sku(sku)}


@app.post("/products", response_model=ProductOut, status_code=201)
def create_product(payload: ProductIn, db: Session = Depends(get_db)):
    repo = ProductRepository(db)
    prod = repo.add(
        # type: ignore[arg-type]
        repo.model(
            nombre=payload.nombre,
            sku=payload.sku,
            precio_compra=payload.precio_compra,
            precio_venta=payload.precio_venta,
            stock_actual=payload.stock_actual,
            unidad_medida=payload.unidad_medida,
            familia=payload.familia,
            image_path=payload.image_path,
            barcode=payload.barcode,
            id_proveedor=payload.id_proveedor,
            id_ubicacion=payload.id_ubicacion,
        )
    )
    db.commit()
    db.refresh(prod)
    return prod


@app.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    repo = ProductRepository(db)
    prod = repo.get(product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return prod


@app.put("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: int, payload: ProductIn, db: Session = Depends(get_db)):
    repo = ProductRepository(db)
    prod = repo.get(product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    for k, v in payload.model_dump().items():
        setattr(prod, k, v)
    db.commit()
    db.refresh(prod)
    return prod


@app.delete("/products/{product_id}", response_model=Message)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    repo = ProductRepository(db)
    try:
        repo.delete(product_id)
        db.commit()
        return Message(message="Producto eliminado")
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------
# Suppliers
# -----------------------------


@app.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db)):
    return SupplierRepository(db).list()


@app.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(payload: SupplierIn, db: Session = Depends(get_db)):
    repo = SupplierRepository(db)
    supplier = repo.add(repo.model(**payload.model_dump()))
    db.commit()
    db.refresh(supplier)
    return supplier


@app.get("/suppliers/{supplier_id}", response_model=SupplierOut)
def get_supplier(supplier_id: int, db: Session = Depends(get_db)):
    repo = SupplierRepository(db)
    obj = repo.get(supplier_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return obj


@app.put("/suppliers/{supplier_id}", response_model=SupplierOut)
def update_supplier(supplier_id: int, payload: SupplierIn, db: Session = Depends(get_db)):
    repo = SupplierRepository(db)
    obj = repo.get(supplier_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@app.delete("/suppliers/{supplier_id}", response_model=Message)
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)):
    repo = SupplierRepository(db)
    repo.delete(supplier_id)
    db.commit()
    return Message(message="Proveedor eliminado")


# -----------------------------
# Customers
# -----------------------------


@app.get("/customers", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    return CustomerRepository(db).list()


@app.post("/customers", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerIn, db: Session = Depends(get_db)):
    repo = CustomerRepository(db)
    obj = repo.add(repo.model(**payload.model_dump()))
    db.commit()
    db.refresh(obj)
    return obj


@app.get("/customers/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    repo = CustomerRepository(db)
    obj = repo.get(customer_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return obj


@app.put("/customers/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, payload: CustomerIn, db: Session = Depends(get_db)):
    repo = CustomerRepository(db)
    obj = repo.get(customer_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@app.delete("/customers/{customer_id}", response_model=Message)
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    repo = CustomerRepository(db)
    repo.delete(customer_id)
    db.commit()
    return Message(message="Cliente eliminado")


# -----------------------------
# Inventory Movements
# -----------------------------


@app.post("/inventory/entries", response_model=Message, status_code=201)
def create_entry(payload: StockEntryIn, db: Session = Depends(get_db)):
    inv = InventoryManager(db)
    try:
        inv.register_entry(
            product_id=payload.product_id,
            cantidad=payload.cantidad,
            motivo=payload.motivo,
            when=payload.when,
            lote=payload.lote,
            serie=payload.serie,
            fecha_vencimiento=payload.fecha_vencimiento,
            reception_id=payload.reception_id,
            location_id=payload.location_id,
        )
        db.commit()
        return Message(message="Entrada registrada")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/inventory/exits", response_model=Message, status_code=201)
def create_exit(payload: StockExitIn, db: Session = Depends(get_db)):
    inv = InventoryManager(db)
    try:
        inv.register_exit(
            product_id=payload.product_id,
            cantidad=payload.cantidad,
            motivo=payload.motivo,
            when=payload.when,
        )
        db.commit()
        return Message(message="Salida registrada")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------
# Purchases
# -----------------------------


@app.post("/purchases", response_model=PurchaseOut, status_code=201)
def create_purchase(payload: PurchaseCreate, db: Session = Depends(get_db)):
    mgr = PurchaseManager(db)
    try:
        purchase = mgr.create_purchase(
            supplier_id=payload.supplier_id,
            items=[
                PurchaseItem(
                    product_id=it.product_id,
                    cantidad=it.cantidad,
                    precio_unitario=it.precio_unitario,
                )
                for it in payload.items
            ],
            fecha=payload.fecha,
            estado=payload.estado,
            apply_to_stock=payload.apply_to_stock,
        )
        return purchase
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/purchases", response_model=list[PurchaseOut])
def list_purchases(
    from_date: str | None = None,
    to_date: str | None = None,
    supplier_id: int | None = None,
    estado: str | None = None,
    db: Session = Depends(get_db),
):
    repo = PurchaseRepository(db)
    q = repo.query()
    from src.data.models import Purchase  # local import for columns
    if from_date:
        q = q.filter(Purchase.fecha_compra >= from_date)
    if to_date:
        q = q.filter(Purchase.fecha_compra <= to_date)
    if supplier_id is not None:
        q = q.filter(Purchase.id_proveedor == supplier_id)
    if estado:
        q = q.filter(Purchase.estado.ilike(estado))
    return list(q.order_by(Purchase.id.desc()).limit(500).all())


@app.get("/purchases/{purchase_id}", response_model=PurchaseWithDetails)
def get_purchase(purchase_id: int, db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload
    from src.data.models import Purchase, PurchaseDetail
    pur = (
        db.query(Purchase)
        .options(joinedload(Purchase.details).joinedload(PurchaseDetail.product))
        .get(purchase_id)
    )
    if not pur:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    # Ensure details loaded
    _ = pur.details  # type: ignore[attr-defined]
    return pur


@app.post("/purchases/{purchase_id}/cancel", response_model=Message)
def cancel_purchase(purchase_id: int, revert_stock: bool = True, db: Session = Depends(get_db)):
    mgr = PurchaseManager(db)
    try:
        mgr.cancel_purchase(purchase_id, revert_stock=revert_stock)
        return Message(message="Compra cancelada")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/purchases/{purchase_id}", response_model=Message)
def delete_purchase(purchase_id: int, revert_stock: bool = True, db: Session = Depends(get_db)):
    mgr = PurchaseManager(db)
    try:
        mgr.delete_purchase(purchase_id, revert_stock=revert_stock)
        return Message(message="Compra eliminada")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------
# Sales
# -----------------------------


@app.post("/sales", response_model=SaleOut, status_code=201)
def create_sale(payload: SaleCreate, db: Session = Depends(get_db)):
    mgr = SalesManager(db)
    try:
        sale = mgr.create_sale(
            customer_id=payload.customer_id,
            items=[
                SaleItem(
                    product_id=it.product_id,
                    cantidad=it.cantidad,
                    precio_unitario=it.precio_unitario,
                )
                for it in payload.items
            ],
            fecha=payload.fecha,
            estado=payload.estado,
            apply_to_stock=payload.apply_to_stock,
        )
        return sale
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/sales", response_model=list[SaleOut])
def list_sales(
    from_date: str | None = None,
    to_date: str | None = None,
    customer_id: int | None = None,
    estado: str | None = None,
    db: Session = Depends(get_db),
):
    repo = SaleRepository(db)
    q = repo.query()
    from src.data.models import Sale  # local for columns
    if from_date:
        q = q.filter(Sale.fecha_venta >= from_date)
    if to_date:
        q = q.filter(Sale.fecha_venta <= to_date)
    if customer_id is not None:
        q = q.filter(Sale.id_cliente == customer_id)
    if estado:
        q = q.filter(Sale.estado.ilike(estado))
    return list(q.order_by(Sale.id.desc()).limit(500).all())


@app.get("/sales/{sale_id}", response_model=SaleWithDetails)
def get_sale(sale_id: int, db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload
    from src.data.models import Sale, SaleDetail
    sale = (
        db.query(Sale)
        .options(joinedload(Sale.details).joinedload(SaleDetail.product))
        .get(sale_id)
    )
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    _ = sale.details
    return sale


@app.post("/sales/{sale_id}/cancel", response_model=Message)
def cancel_sale(sale_id: int, revert_stock: bool = True, db: Session = Depends(get_db)):
    mgr = SalesManager(db)
    try:
        mgr.cancel_sale(sale_id, revert_stock=revert_stock)
        return Message(message="Venta cancelada")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/sales/{sale_id}", response_model=Message)
def delete_sale(sale_id: int, revert_stock: bool = True, db: Session = Depends(get_db)):
    mgr = SalesManager(db)
    try:
        mgr.delete_sale(sale_id, revert_stock=revert_stock)
        return Message(message="Venta eliminada")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------
# Locations
# -----------------------------


@app.get("/locations", response_model=list[LocationOut])
def list_locations(db: Session = Depends(get_db)):
    return LocationRepository(db).list()


@app.post("/locations", response_model=LocationOut, status_code=201)
def create_location(payload: LocationIn, db: Session = Depends(get_db)):
    repo = LocationRepository(db)
    obj = repo.add(repo.model(**payload.model_dump()))
    db.commit()
    db.refresh(obj)
    return obj


@app.put("/locations/{location_id}", response_model=LocationOut)
def update_location(location_id: int, payload: LocationIn, db: Session = Depends(get_db)):
    repo = LocationRepository(db)
    obj = repo.get(location_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Ubicación no encontrada")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@app.delete("/locations/{location_id}", response_model=Message)
def delete_location(location_id: int, db: Session = Depends(get_db)):
    repo = LocationRepository(db)
    repo.delete(location_id)
    db.commit()
    return Message(message="Ubicación eliminada")


# -----------------------------
# Reports (Sales)
# -----------------------------


@app.get("/reports/sales", response_model=list[SalesReportItem])
def sales_report(
    from_date: str,
    to_date: str,
    customer_id: int | None = None,
    product_id: int | None = None,
    estado: str | None = None,
    db: Session = Depends(get_db),
):
    from sqlalchemy import and_, or_
    from src.data.models import Sale, SaleDetail, Customer

    q = db.query(Sale)
    q = q.filter(and_(Sale.fecha_venta >= from_date, Sale.fecha_venta <= to_date))
    if customer_id is not None:
        q = q.filter(Sale.id_cliente == customer_id)
    if estado:
        q = q.filter(Sale.estado.ilike(estado))
    if product_id is not None:
        q = q.join(Sale.details).filter(SaleDetail.id_producto == product_id)
    q = q.join(Sale.customer)

    rows = q.with_entities(
        Sale.id,
        Sale.fecha_venta,
        Customer.razon_social.label("cliente"),
        Sale.estado,
        Sale.total_venta,
    ).order_by(Sale.fecha_venta.asc()).all()

    return [
        SalesReportItem(
            id=r[0],
            fecha_venta=r[1],
            cliente=r[2],
            estado=r[3],
            total_venta=r[4],
        )
        for r in rows
    ]


@app.get("/reports/sales.csv")
def sales_report_csv(
    from_date: str,
    to_date: str,
    customer_id: int | None = None,
    product_id: int | None = None,
    estado: str | None = None,
    db: Session = Depends(get_db),
):
    # Reutiliza la consulta del JSON
    from sqlalchemy import and_
    from src.data.models import Sale, SaleDetail, Customer

    q = db.query(Sale)
    q = q.filter(and_(Sale.fecha_venta >= from_date, Sale.fecha_venta <= to_date))
    if customer_id is not None:
        q = q.filter(Sale.id_cliente == customer_id)
    if estado:
        q = q.filter(Sale.estado.ilike(estado))
    if product_id is not None:
        q = q.join(Sale.details).filter(SaleDetail.id_producto == product_id)
    q = q.join(Sale.customer)

    rows = q.with_entities(
        Sale.id,
        Sale.fecha_venta,
        Customer.razon_social,
        Sale.estado,
        Sale.total_venta,
    ).order_by(Sale.fecha_venta.asc()).all()

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "Fecha", "Cliente", "Estado", "Total"])
    for r in rows:
        writer.writerow([r[0], r[1].isoformat() if hasattr(r[1], 'isoformat') else r[1], r[2], r[3], str(r[4])])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename=ventas_{from_date}_{to_date}.csv"
    })


@app.get("/reports/sales.pdf")
def sales_report_pdf(
    from_date: str,
    to_date: str,
    customer_id: int | None = None,
    product_id: int | None = None,
    estado: str | None = None,
    db: Session = Depends(get_db),
):
    from sqlalchemy import and_
    from src.data.models import Sale, SaleDetail, Customer, Product
    from src.reports.sales_report_pdf import _downloads_dir, _read_company_cfg, _venta_page_story
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.units import mm
    from tempfile import NamedTemporaryFile

    q = db.query(Sale)
    q = q.filter(and_(Sale.fecha_venta >= from_date, Sale.fecha_venta <= to_date))
    if customer_id is not None:
        q = q.filter(Sale.id_cliente == customer_id)
    if estado:
        q = q.filter(Sale.estado.ilike(estado))
    if product_id is not None:
        q = q.join(Sale.details).filter(SaleDetail.id_producto == product_id)
    q = q.join(Sale.customer)

    rows = q.with_entities(
        Sale.id,
        Sale.fecha_venta,
        Customer.razon_social.label("cliente"),
        Customer.rut.label("cliente_rut"),
        Customer.direccion.label("cliente_direccion"),
        Customer.telefono.label("cliente_telefono"),
        Customer.email.label("cliente_email"),
        Sale.estado,
        Sale.total_venta,
    ).order_by(Sale.fecha_venta.asc()).all()

    with NamedTemporaryFile(suffix=".pdf") as tmp:
        doc = SimpleDocTemplate(tmp.name, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=14*mm, bottomMargin=14*mm)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle("small", fontSize=9, leading=11))
        styles.add(ParagraphStyle("h_med", fontSize=12, leading=14))
        styles.add(ParagraphStyle("h_doc", fontSize=16, leading=18, alignment=1))
        company = _read_company_cfg()
        story = []
        story.append(Paragraph("Informe de Ventas", styles["h_doc"]))
        story.append(Spacer(1, 6))
        for r in rows:
            sale_id = r[0]
            sale_date = r[1]
            cust_name = r[2]
            cust_rut = r[3]
            cust_dir = r[4]
            cust_tel = r[5]
            cust_mail = r[6]
            # Items
            dets = (
                db.query(SaleDetail, Product)
                .join(Product, SaleDetail.id_producto == Product.id)
                .filter(SaleDetail.id_venta == sale_id)
                .all()
            )
            items = [
                {
                    "codigo": p.sku,
                    "descripcion": p.nombre,
                    "cantidad": d.cantidad,
                    "precio": float(d.precio_unitario),
                    "subtotal": float(d.subtotal),
                }
                for (d, p) in ((dp[0], dp[1]) for dp in dets)
            ]
            row = {
                "id": sale_id,
                "fecha": sale_date,
                "cliente": cust_name,
                "cliente_rut": cust_rut,
                "cliente_direccion": cust_dir,
                "cliente_telefono": cust_tel,
                "cliente_email": cust_mail,
                "items": items,
            }
            story += _venta_page_story(row, styles, company)
        doc.build(story)
        tmp.seek(0)
        return StreamingResponse(tmp.read(), media_type="application/pdf", headers={"Content-Disposition": f"inline; filename=ventas_{from_date}_{to_date}.pdf"})



# -----------------------------
# Inventory: stock + thresholds
# -----------------------------


@app.get("/inventory/stock", response_model=list[InventoryItemOut])
def inventory_stock(q: str | None = None, supplier_id: int | None = None, db: Session = Depends(get_db)):
    from src.data.models import Product
    from src.utils.inventory_thresholds import get_thresholds

    query = db.query(Product)
    if q:
        qnorm = f"%{q.lower().strip()}%"
        query = query.filter((Product.nombre.ilike(qnorm)) | (Product.sku.ilike(qnorm)))
    if supplier_id is not None:
        query = query.filter(Product.id_proveedor == supplier_id)
    rows = query.order_by(Product.nombre.asc()).limit(1000).all()

    out: list[InventoryItemOut] = []
    for p in rows:
        mn, mx = get_thresholds(p.id, 0, 0)
        below = mn is not None and int(p.stock_actual or 0) < int(mn)
        out.append(InventoryItemOut(
            id=p.id,
            nombre=p.nombre,
            sku=p.sku,
            stock_actual=int(p.stock_actual or 0),
            id_proveedor=p.id_proveedor,
            id_ubicacion=p.id_ubicacion,
            familia=p.familia,
            min_threshold=mn,
            max_threshold=mx,
            below_min=below,
        ))
    return out


@app.get("/inventory/thresholds/{product_id}", response_model=ThresholdOut)
def get_threshold(product_id: int):
    from src.utils.inventory_thresholds import get_thresholds
    mn, mx = get_thresholds(product_id, 0, 0)
    return ThresholdOut(product_id=product_id, min_value=int(mn), max_value=int(mx))


@app.post("/inventory/thresholds/{product_id}", response_model=ThresholdOut)
def set_threshold(product_id: int, payload: ThresholdIn):
    from src.utils.inventory_thresholds import set_thresholds
    set_thresholds(product_id, payload.min_value, payload.max_value)
    return ThresholdOut(product_id=product_id, min_value=payload.min_value, max_value=payload.max_value)


@app.get("/reports/inventory.xlsx")
def inventory_xlsx(
    report_type: str = "venta",  # venta | compra | completo
    nombre_contains: str | None = None,
    sku_contains: str | None = None,
    stock_min: int | None = None,
    stock_max: int | None = None,
    solo_bajo_minimo: bool = False,
    solo_sobre_maximo: bool = False,
    order_by: str = "nombre",
    order_asc: bool = True,
    db: Session = Depends(get_db),
):
    from src.reports.inventory_reports import InventoryFilter, InventoryReportService
    from tempfile import NamedTemporaryFile
    svc = InventoryReportService(db)
    flt = InventoryFilter(
        nombre_contains=nombre_contains or None,
        sku_contains=sku_contains or None,
        stock_min=stock_min,
        stock_max=stock_max,
        solo_bajo_minimo=solo_bajo_minimo,
        solo_sobre_maximo=solo_sobre_maximo,
        order_by=order_by,
        order_asc=order_asc,
        report_type=report_type if report_type in ("venta", "compra", "completo") else "venta",
    )
    rows = svc.fetch(flt)
    # export_xlsx escribe a un archivo nuevo; lo leemos y devolvemos
    out_path = svc.export_xlsx(rows, flt, title="Inventario")
    data = out_path.read_bytes()
    try:
        out_path.unlink(missing_ok=True)
    except Exception:
        pass
    return StreamingResponse(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=inventory_{report_type}.xlsx"},
    )


# -----------------------------
# PDF Generation (PO/OV)
# -----------------------------


@app.get("/purchases/{purchase_id}/pdf")
def purchase_pdf(purchase_id: int, db: Session = Depends(get_db)):
    from src.data.models import Purchase, Supplier, PurchaseDetail, Product
    from src.utils.po_generator import generate_po_pdf

    pur = db.query(Purchase).get(purchase_id)
    if not pur:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    supplier = db.query(Supplier).get(pur.id_proveedor)
    if not supplier:
        raise HTTPException(status_code=400, detail="Proveedor no encontrado")
    details = (
        db.query(PurchaseDetail, Product)
        .join(Product, PurchaseDetail.id_producto == Product.id)
        .filter(PurchaseDetail.id_compra == purchase_id)
        .all()
    )

    items = [
        {
            "id": d.id_producto,
            "nombre": p.nombre,
            "unidad": p.unidad_medida or "U",
            "cantidad": d.cantidad,
            # Generadores usan 'precio' BRUTO (con IVA)
            "precio": float(d.precio_unitario),
            "subtotal": float(d.subtotal),
        }
        for (d, p) in ((dp[0], dp[1]) for dp in details)
    ]

    sup_payload = {
        "nombre": supplier.razon_social,
        "rut": supplier.rut,
        "contacto": supplier.contacto,
        "telefono": supplier.telefono,
        "email": supplier.email,
        "direccion": supplier.direccion,
    }

    with NamedTemporaryFile(suffix=".pdf") as tmp:
        generate_po_pdf(
            output_path=tmp.name,
            po_number=str(purchase_id),
            supplier=sup_payload,
            items=items,
            currency="CLP",
            notes=None,
        )
        tmp.seek(0)
        return StreamingResponse(
            tmp.read(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=OC_{purchase_id}.pdf",
            },
        )


@app.get("/sales/{sale_id}/pdf")
def sale_pdf(sale_id: int, db: Session = Depends(get_db)):
    from src.data.models import Sale, Customer, SaleDetail, Product
    from src.utils.so_generator import generate_so_pdf

    sale = db.query(Sale).get(sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    customer = db.query(Customer).get(sale.id_cliente)
    if not customer:
        raise HTTPException(status_code=400, detail="Cliente no encontrado")
    details = (
        db.query(SaleDetail, Product)
        .join(Product, SaleDetail.id_producto == Product.id)
        .filter(SaleDetail.id_venta == sale_id)
        .all()
    )
    items = [
        {
            "id": d.id_producto,
            "nombre": p.nombre,
            "unidad": p.unidad_medida or "U",
            "cantidad": d.cantidad,
            # Generadores esperan precio BRUTO
            "precio": float(d.precio_unitario),
            "subtotal": float(d.subtotal),
        }
        for (d, p) in ((dp[0], dp[1]) for dp in details)
    ]

    cust_payload = {
        "nombre": customer.razon_social,
        "rut": customer.rut,
        "contacto": customer.contacto,
        "telefono": customer.telefono,
        "email": customer.email,
        "direccion": customer.direccion,
    }

    with NamedTemporaryFile(suffix=".pdf") as tmp:
        generate_so_pdf(
            output_path=tmp.name,
            so_number=str(sale_id),
            customer=cust_payload,
            items=items,
            currency="CLP",
            notes=None,
        )
        tmp.seek(0)
        return StreamingResponse(
            tmp.read(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=OV_{sale_id}.pdf",
            },
        )


@app.post("/documents/quote.pdf")
def quote_pdf(payload: QuoteCreate):
    from src.utils.quote_generator import generate_quote_to_downloads, generate_quote_to_downloads as _gen
    # Usamos NamedTemporaryFile y generate_quote_to_downloads -> genera en descargas, por lo que preferimos un tmp directo
    # Aquí generamos a un archivo temporal usando reportlab directamente reusando la función generate_quote_to_downloads
    from tempfile import NamedTemporaryFile
    from src.utils.helpers import get_downloads_dir
    from src.utils.quote_generator import _band  # noqa
    # Generar a archivo temporal (evitar escribir en Descargas del servidor)
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Spacer, Table
    from reportlab.lib.styles import ParagraphStyle
    from src.utils.quote_generator import _header, _items_table_net, _totals_block
    from src.utils.helpers import get_company_info, get_po_payment_method

    with NamedTemporaryFile(suffix=".pdf") as tmp:
        company = get_company_info()
        doc = SimpleDocTemplate(
            tmp.name,
            pagesize=A4,
            leftMargin=14 * mm, rightMargin=14 * mm,
            topMargin=14 * mm, bottomMargin=14 * mm,
            title="Cotización", author="Inventario App",
        )
        story = []
        story.append(_header(company, payload.quote_number))
        story.append(Spacer(1, 4))
        warn = ParagraphStyle(name="warn", fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#1E6AA8"), alignment=1)
        story.append(Paragraph("*Documento sujeto a modificación (Provisorio)*", warn))
        story.append(Spacer(1, 4))

        # Detalles
        story.append(_band("Detalles generales"))
        story.append(Spacer(1, 2))
        p = ParagraphStyle(name="p", fontName="Helvetica", fontSize=10, leading=13)
        left_lines = [
            ("Señor(es):", payload.supplier.nombre or "-"),
            ("Atención:", payload.supplier.contacto or "-"),
            ("Teléfono:", payload.supplier.telefono or "-"),
            ("Dirección:", payload.supplier.direccion or "-"),
        ]
        right_lines = [
            ("Forma de Pago:", payload.supplier.pago or get_po_payment_method()),
        ]
        def _two_col(rows, w_label_mm: float, w_val_mm: float):
            data = []
            for a, b in rows:
                data.append([Paragraph(f"<b>{a}</b>", p), Paragraph(str(b), p)])
            return Table(data, colWidths=[w_label_mm * mm, w_val_mm * mm])
        details = Table([[ _two_col(left_lines, 34, 78), _two_col(right_lines, 28, 40) ]], colWidths=[112 * mm, 68 * mm])
        story.append(details)
        story.append(Spacer(1, 4))

        # Items + totales
        items = [dict(id=it.id, nombre=it.nombre, unidad=it.unidad or "U", cantidad=float(it.cantidad), precio=float(it.precio), dcto=float(it.dcto or 0), subtotal=float(it.subtotal or (float(it.cantidad) * float(it.precio)))) for it in payload.items]
        story.append(_items_table_net(items, payload.currency))
        story.append(Spacer(1, 4))
        story += _totals_block(company, items, payload.currency)

        if payload.notes:
            story.append(Spacer(1, 3))
            story.append(_band("Observaciones:"))
            story.append(Spacer(1, 2))
            story.append(Paragraph(payload.notes, p))

        doc.build(story)
        tmp.seek(0)
        return StreamingResponse(
            tmp.read(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=COT_{payload.quote_number}.pdf",
            },
        )


# -----------------------------
# Receptions
# -----------------------------


@app.post("/receptions", response_model=ReceptionOut, status_code=201)
def create_reception(payload: ReceptionCreate, db: Session = Depends(get_db)):
    from datetime import datetime as _dt
    from sqlalchemy import and_
    from src.data.models import Purchase, PurchaseDetail, Product, Reception, StockEntry

    pur = db.query(Purchase).get(payload.purchase_id)
    if not pur:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if not payload.items:
        raise HTTPException(status_code=400, detail="Sin ítems para recepcionar")

    rec = Reception(
        id_compra=pur.id,
        tipo_doc=payload.tipo_doc,
        numero_documento=payload.numero_documento,
        fecha=payload.fecha or _dt.utcnow(),
    )
    db.add(rec)
    db.flush()

    for it in payload.items:
        if it.received_qty <= 0:
            raise HTTPException(status_code=400, detail=f"Cantidad inválida para producto {it.product_id}")
        det: PurchaseDetail | None = (
            db.query(PurchaseDetail)
            .filter(and_(PurchaseDetail.id_compra == pur.id, PurchaseDetail.id_producto == it.product_id))
            .first()
        )
        if not det:
            raise HTTPException(status_code=400, detail=f"Producto {it.product_id} no está en la compra {pur.id}")
        remaining = int(det.cantidad or 0) - int(det.received_qty or 0)
        if it.received_qty > max(0, remaining):
            raise HTTPException(status_code=400, detail=f"Recepción excede lo comprado. Prod {it.product_id}: queda {remaining}")

        if payload.apply_to_stock:
            se = StockEntry(
                id_producto=it.product_id,
                id_ubicacion=it.id_ubicacion,
                id_recepcion=rec.id,
                cantidad=int(it.received_qty),
                motivo=f"Recepción OC {pur.id}",
                lote=(it.lote or None),
                serie=(it.serie or None),
                fecha_vencimiento=it.fecha_vencimiento,
                fecha=payload.fecha or _dt.utcnow(),
            )
            db.add(se)

        det.received_qty = int(det.received_qty or 0) + int(it.received_qty)
        if payload.apply_to_stock:
            prod = db.query(Product).get(it.product_id)
            if prod:
                prod.stock_actual = int(prod.stock_actual or 0) + int(it.received_qty)

    if payload.update_status and getattr(pur, "estado", "").lower() not in ("cancelada", "eliminada"):
        totals = db.query(PurchaseDetail).filter(PurchaseDetail.id_compra == pur.id).all()
        all_received = all(int(d.received_qty or 0) >= int(d.cantidad or 0) for d in totals)
        any_received = any(int(d.received_qty or 0) > 0 for d in totals)
        if all_received:
            pur.estado = "Completada"
        elif any_received and pur.estado.lower() == "pendiente":
            pur.estado = "Incompleta"

    db.commit()
    db.refresh(rec)
    return rec


@app.get("/receptions", response_model=list[ReceptionOut])
def list_receptions(db: Session = Depends(get_db)):
    from src.data.models import Reception
    q = db.query(Reception).order_by(Reception.id.desc()).limit(500)
    return list(q.all())


# -----------------------------
# Catalog PDF
# -----------------------------


@app.get("/reports/catalog.pdf")
def catalog_pdf():
    from tempfile import NamedTemporaryFile
    from pathlib import Path as _Path
    from src.reports.catalog_generator import generate_products_catalog
    with NamedTemporaryFile(suffix=".pdf") as tmp:
        out = generate_products_catalog(out_path=_Path(tmp.name), auto_open=False)
        data = _Path(out).read_bytes() if hasattr(out, 'read_bytes') else _Path(tmp.name).read_bytes()
        return StreamingResponse(
            data,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=catalogo_productos.pdf"},
        )


@app.get("/receptions/{rec_id}", response_model=ReceptionOut)
def get_reception(rec_id: int, db: Session = Depends(get_db)):
    from src.data.models import Reception
    rec = db.query(Reception).get(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recepción no encontrada")
    return rec


@app.get("/purchases/{purchase_id}/receptions", response_model=list[ReceptionOut])
def list_receptions_by_purchase(purchase_id: int, db: Session = Depends(get_db)):
    from src.data.models import Reception
    q = db.query(Reception).filter(Reception.id_compra == purchase_id).order_by(Reception.id.desc())
    return list(q.all())
