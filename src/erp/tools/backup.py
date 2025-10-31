from __future__ import annotations
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional
import sqlite3
from datetime import datetime

from openpyxl import Workbook, load_workbook

from src.erp.core.database import get_connection, init_db, DEFAULT_DB_PATH
from src.data.database import get_session
from src.data.models import (
    Product, Customer, Supplier,
    Purchase, PurchaseDetail,
    Sale, SaleDetail,
    Reception,
    StockEntry, StockExit,
    Location,
)
from src.utils.helpers import get_downloads_dir, unique_path


def _rows(conn: sqlite3.Connection, sql: str) -> List[sqlite3.Row]:
    cur = conn.execute(sql)
    return list(cur.fetchall())


def export_erp_to_xlsx(out_path: Optional[Path] = None, *, auto_open: bool = True) -> Path:
    # Usar el mismo archivo que emplea la app (DEFAULT_DB_PATH)
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        init_db(conn)
    except Exception:
        pass

    docs = _rows(conn, "SELECT * FROM documentos ORDER BY id ASC")
    dets = _rows(conn, "SELECT * FROM detalles ORDER BY id ASC")
    logs = _rows(conn, "SELECT * FROM log_auditoria ORDER BY id ASC")

    wb = Workbook()
    ws_meta = wb.active
    ws_meta.title = "meta"
    ws_meta["A1"] = "generated_at"
    ws_meta["B1"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _write_sheet(name: str, rows: List[sqlite3.Row]):
        ws = wb.create_sheet(title=name)
        if not rows:
            return
        cols = rows[0].keys()
        ws.append(list(cols))
        for r in rows:
            ws.append([r[c] for c in cols])

    _write_sheet("documentos", docs)
    _write_sheet("detalles", dets)
    _write_sheet("log_auditoria", logs)

    # save
    if out_path is None:
        out_dir = get_downloads_dir()
        out_path = unique_path(out_dir, f"ERP_backup_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)

    if auto_open:
        try:
            import webbrowser
            webbrowser.open(str(out_path))
        except Exception:
            pass
    return out_path


def import_erp_from_xlsx(xlsx_path: Path) -> None:
    if not Path(xlsx_path).exists():
        raise FileNotFoundError(xlsx_path)
    # Importar sobre el mismo archivo ERP usado por la app
    conn = get_connection(DEFAULT_DB_PATH)
    init_db(conn)
    wb = load_workbook(filename=str(xlsx_path))

    def _read_sheet(name: str) -> List[Dict[str, Any]]:
        if name not in wb.sheetnames:
            return []
        ws = wb[name]
        rows = list(ws.values)
        if not rows:
            return []
        headers = [str(h) for h in rows[0]]
        out: List[Dict[str, Any]] = []
        for r in rows[1:]:
            if r is None:
                continue
            rec = {headers[i]: r[i] if i < len(r) else None for i in range(len(headers))}
            out.append(rec)
        return out

    documentos = _read_sheet("documentos")
    detalles = _read_sheet("detalles")
    logs = _read_sheet("log_auditoria")

    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")
    # limpiar en orden seguro
    cur.execute("DELETE FROM detalles;")
    cur.execute("DELETE FROM documentos;")
    cur.execute("DELETE FROM log_auditoria;")

    # insertar documentos
    if documentos:
        cols = list(documentos[0].keys())
        placeholders = ",".join([":" + c for c in cols])
        sql = f"INSERT INTO documentos ({','.join(cols)}) VALUES ({placeholders})"
        cur.executemany(sql, documentos)

    # insertar detalles (dependen de documentos)
    if detalles:
        cols = list(detalles[0].keys())
        placeholders = ",".join([":" + c for c in cols])
        sql = f"INSERT INTO detalles ({','.join(cols)}) VALUES ({placeholders})"
        cur.executemany(sql, detalles)

    # logs
    if logs:
        cols = list(logs[0].keys())
        placeholders = ",".join([":" + c for c in cols])
        sql = f"INSERT INTO log_auditoria ({','.join(cols)}) VALUES ({placeholders})"
        cur.executemany(sql, logs)

    conn.commit()


# =================== APP BACKUP (ORM) =================== #
def _to_val(v):
    try:
        from decimal import Decimal
        if isinstance(v, Decimal):
            return float(v)
        return v
    except Exception:
        return v


def export_app_backup_to_xlsx(out_path: Optional[Path] = None, *, auto_open: bool = True) -> Path:
    """Exporta 5 hojas: productos, clientes, proveedores, ordenes, inventario."""
    sess = get_session()

    # 1) Crear libro y meta
    wb = Workbook()
    ws_meta = wb.active
    ws_meta.title = "meta"
    ws_meta["A1"] = "generated_at"
    ws_meta["B1"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 2) Ubicaciones
    ws = wb.create_sheet("ubicaciones")
    loc_cols = ["id", "nombre", "descripcion"]
    ws.append(loc_cols)
    for l in sess.query(Location).order_by(Location.id.asc()).all():
        ws.append([l.id, l.nombre, getattr(l, 'descripcion', None) or ""])

    # 3) Productos
    ws = wb.create_sheet("productos")
    prod_cols = [
        "id","nombre","sku","precio_compra","precio_venta","stock_actual",
        "unidad_medida","id_proveedor","id_ubicacion","image_path"
    ]
    ws.append(prod_cols)
    for p in sess.query(Product).order_by(Product.id.asc()).all():
        ws.append([
            p.id, p.nombre, p.sku,
            _to_val(getattr(p, 'precio_compra', 0)),
            _to_val(getattr(p, 'precio_venta', 0)),
            getattr(p, 'stock_actual', 0),
            getattr(p, 'unidad_medida', None) or "",
            getattr(p, 'id_proveedor', None),
            getattr(p, 'id_ubicacion', None),
            getattr(p, 'image_path', None) or "",
        ])

    # 4) Clientes
    ws = wb.create_sheet("clientes")
    cust_cols = ["id","razon_social","rut","contacto","telefono","email","direccion"]
    ws.append(cust_cols)
    for c in sess.query(Customer).order_by(Customer.id.asc()).all():
        ws.append([
            c.id, c.razon_social, c.rut,
            getattr(c,'contacto',None) or "",
            getattr(c,'telefono',None) or "",
            getattr(c,'email',None) or "",
            getattr(c,'direccion',None) or "",
        ])

    # 5) Proveedores
    ws = wb.create_sheet("proveedores")
    sup_cols = ["id","razon_social","rut","contacto","telefono","email","direccion"]
    ws.append(sup_cols)
    for s in sess.query(Supplier).order_by(Supplier.id.asc()).all():
        ws.append([
            s.id, s.razon_social, s.rut,
            getattr(s,'contacto',None) or "",
            getattr(s,'telefono',None) or "",
            getattr(s,'email',None) or "",
            getattr(s,'direccion',None) or "",
        ])

    # 6) Ordenes (todas: compras, ventas y recepciones)
    ws = wb.create_sheet("ordenes")
    order_cols = [
        # genéricos
        "tipo", "id", "fecha", "estado", "total",
        # tercero
        "tercero_tipo", "tercero_id", "tercero_nombre",
        # documento asociado (si aplica)
        "doc_tipo", "doc_numero",
        # vínculos específicos
        "oc_id",    # para compras/recepciones
        "ov_id",    # para ventas
        # campos adicionales de compra
        "referencia", "moneda", "tasa_cambio", "unidad_negocio", "proporcionalidad", "stock_policy"
    ]
    ws.append(order_cols)

    # Compras
    for pur, sup in (
        sess.query(Purchase, Supplier)
        .join(Supplier, Supplier.id == Purchase.id_proveedor)
        .order_by(Purchase.id.asc())
        .all()
    ):
        ws.append([
            "compra",
            pur.id,
            getattr(pur, 'fecha_compra', None),
            getattr(pur, 'estado', None) or "",
            _to_val(getattr(pur, 'total_compra', 0)),
            "proveedor",
            getattr(pur, 'id_proveedor', None),
            getattr(sup, 'razon_social', None) or "",
            "",
            getattr(pur, 'numero_documento', None) or "",
            getattr(pur, 'id', None),   # oc_id
            None,                       # ov_id vacío
            getattr(pur, 'referencia', None) or "",
            getattr(pur, 'moneda', None) or "",
            _to_val(getattr(pur, 'tasa_cambio', None)),
            getattr(pur, 'unidad_negocio', None) or "",
            getattr(pur, 'proporcionalidad', None) or "",
            getattr(pur, 'stock_policy', None) or "",
        ])

    # Ventas
    for sale, cust in (
        sess.query(Sale, Customer)
        .join(Customer, Customer.id == Sale.id_cliente)
        .order_by(Sale.id.asc())
        .all()
    ):
        ws.append([
            "venta",
            sale.id,
            getattr(sale, 'fecha_venta', None),
            getattr(sale, 'estado', None) or "",
            _to_val(getattr(sale, 'total_venta', 0)),
            "cliente",
            getattr(sale, 'id_cliente', None),
            getattr(cust, 'razon_social', None) or getattr(cust, 'rut', None) or "",
            "",
            "",
            None,               # oc_id
            getattr(sale, 'id', None),  # ov_id
            "",
            "",
            None,
            "",
            "",
            "",
        ])

    # Recepciones
    for rec, pur, sup in (
        sess.query(Reception, Purchase, Supplier)
        .join(Purchase, Purchase.id == Reception.id_compra)
        .join(Supplier, Supplier.id == Purchase.id_proveedor)
        .order_by(Reception.id.asc())
        .all()
    ):
        ws.append([
            "recepcion",
            rec.id,
            getattr(rec, 'fecha', None),
            getattr(pur, 'estado', None) or "",
            _to_val(getattr(pur, 'total_compra', 0)),
            "proveedor",
            getattr(pur, 'id_proveedor', None),
            getattr(sup, 'razon_social', None) or "",
            getattr(rec, 'tipo_doc', None) or "",
            getattr(rec, 'numero_documento', None) or "",
            getattr(pur, 'id', None),   # oc_id
            None,                       # ov_id
            getattr(pur, 'referencia', None) or "",
            getattr(pur, 'moneda', None) or "",
            _to_val(getattr(pur, 'tasa_cambio', None)),
            getattr(pur, 'unidad_negocio', None) or "",
            getattr(pur, 'proporcionalidad', None) or "",
            getattr(pur, 'stock_policy', None) or "",
        ])

    # 7) Inventario (snapshot de cantidades por producto)
    # Nota: el usuario solicitó que sea por cantidad (no movimientos E/S)
    ws = wb.create_sheet("inventario")
    inv_cols = ["id_producto", "sku", "nombre", "stock_actual", "id_ubicacion"]
    ws.append(inv_cols)
    for p in sess.query(Product).order_by(Product.id.asc()).all():
        ws.append([
            p.id,
            getattr(p, 'sku', None) or "",
            getattr(p, 'nombre', None) or "",
            getattr(p, 'stock_actual', 0) or 0,
            getattr(p, 'id_ubicacion', None),
        ])

    # Guardar
    if out_path is None:
        out_dir = get_downloads_dir()
        out_path = unique_path(out_dir, f"APP_backup_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)

    if auto_open:
        try:
            import webbrowser
            webbrowser.open(str(out_path))
        except Exception:
            pass
    return out_path


def import_app_backup_from_xlsx(xlsx_path: Path, *, reset: bool = True) -> None:
    """
    Importa un backup APP generado por export_app_backup_to_xlsx.

    Estrategia:
    - (Opcional) Limpia tablas dependientes: movimientos/detalles/recepciones/ventas/compras,
      luego base: productos/proveedores/clientes. No elimina ubicaciones.
    - Inserta proveedores, clientes, productos (con IDs del archivo).
    - Inserta órdenes (cabeceras): compras, ventas, recepciones (sin detalles).
    - Aplica snapshot de stock desde la hoja "inventario" a Product.stock_actual.

    Nota: Al no incluir detalles de órdenes ni movimientos, esta restauración es de estado
    actual (ubicaciones, cabeceras + cantidades por producto), suficiente para levantar el sistema.
    """
    p = Path(xlsx_path)
    if not p.exists():
        raise FileNotFoundError(p)

    wb = load_workbook(filename=str(p))

    def _read(name: str) -> list[dict]:
        if name not in wb.sheetnames:
            return []
        ws = wb[name]
        rows = list(ws.values)
        if not rows:
            return []
        headers = [str(h) if h is not None else "" for h in rows[0]]
        out: list[dict] = []
        for r in rows[1:]:
            if r is None:
                continue
            out.append({headers[i]: r[i] if i < len(r) else None for i in range(len(headers))})
        return out

    sess = get_session()
    try:
        if reset:
            # Orden seguro respetando FKs
            sess.query(StockEntry).delete()
            sess.query(StockExit).delete()
            sess.query(SaleDetail).delete()
            sess.query(PurchaseDetail).delete()
            try:
                sess.query(Reception).delete()
            except Exception:
                pass
            sess.query(Sale).delete()
            sess.query(Purchase).delete()
            sess.query(Product).delete()
            sess.query(Supplier).delete()
            sess.query(Customer).delete()
            # Eliminar ubicaciones al final, cuando no quedan productos referenciándolas
            try:
                sess.query(Location).delete()
            except Exception:
                pass
            sess.commit()

        # Ubicaciones
        for r in _read("ubicaciones"):
            try:
                loc = Location(
                    id=int(r.get("id")),
                    nombre=str(r.get("nombre") or f"Ubicacion {r.get('id')}") or f"Ubicacion {r.get('id')}",
                    descripcion=r.get("descripcion") or None,
                )
                sess.add(loc)
            except Exception:
                pass
        sess.flush()

        # Proveedores
        for r in _read("proveedores"):
            try:
                sup = Supplier(
                    id=int(r.get("id")),
                    razon_social=str(r.get("razon_social") or ""),
                    rut=str(r.get("rut") or f"FAKE-{r.get('id')}") or f"FAKE-{r.get('id')}",
                    contacto=r.get("contacto"), telefono=r.get("telefono"),
                    email=r.get("email"), direccion=r.get("direccion"),
                )
                sess.add(sup)
            except Exception:
                pass
        sess.flush()

        # Clientes
        for r in _read("clientes"):
            try:
                cust = Customer(
                    id=int(r.get("id")),
                    razon_social=str(r.get("razon_social") or r.get("nombre") or ""),
                    rut=str(r.get("rut") or f"FAKE-{r.get('id')}") or f"FAKE-{r.get('id')}",
                    contacto=r.get("contacto"), telefono=r.get("telefono"),
                    email=r.get("email"), direccion=r.get("direccion"),
                )
                sess.add(cust)
            except Exception:
                pass
        sess.flush()

        # Cache de ubicaciones existentes (ids)
        existing_locations = {int(l.id) for l in sess.query(Location.id).all()} if sess.bind else set()

        # Productos
        default_sup_id: Optional[int] = None
        for r in _read("productos"):
            try:
                # Resolver proveedor: garantizar FK válido
                prov_id = int(r.get("id_proveedor")) if r.get("id_proveedor") is not None else None
                if prov_id is None or sess.get(Supplier, prov_id) is None:
                    if prov_id is None:
                        # Usar/crear proveedor por defecto
                        if default_sup_id is None:
                            try:
                                existing_def = sess.query(Supplier).filter(Supplier.rut == "FAKE-DEFAULT").first()
                            except Exception:
                                existing_def = None
                            if existing_def is None:
                                sup_def = Supplier(razon_social="Proveedor Importado", rut="FAKE-DEFAULT")
                                sess.add(sup_def)
                                sess.flush()
                                default_sup_id = int(sup_def.id)
                            else:
                                default_sup_id = int(existing_def.id)
                        prov_id = default_sup_id
                    else:
                        # Crear stub con el ID esperado
                        sup_stub = Supplier(id=prov_id, razon_social=f"Proveedor {prov_id}", rut=f"FAKE-{prov_id}")
                        sess.add(sup_stub)
                        sess.flush()

                # Resolver ubicación: si no existe, dejar en None
                loc_id = int(r.get("id_ubicacion")) if r.get("id_ubicacion") is not None else None
                if loc_id is not None and loc_id not in existing_locations:
                    loc_id = None

                prod = Product(
                    id=int(r.get("id")),
                    nombre=str(r.get("nombre") or ""),
                    sku=str(r.get("sku") or f"SKU-{r.get('id')}") or f"SKU-{r.get('id')}",
                    precio_compra=_to_val(r.get("precio_compra")) or 0,
                    precio_venta=_to_val(r.get("precio_venta")) or 0,
                    stock_actual=int(r.get("stock_actual") or 0),
                    unidad_medida=r.get("unidad_medida") or None,
                    id_proveedor=int(prov_id),
                    id_ubicacion=loc_id,
                    image_path=r.get("image_path") or None,
                    barcode=r.get("barcode") if "barcode" in r else None,
                )
                sess.add(prod)
            except Exception:
                pass
        sess.flush()

        # Órdenes: compras, ventas y recepciones
        for r in _read("ordenes"):
            try:
                tipo = (str(r.get("tipo") or "").strip().lower())
                if tipo == "compra":
                    pur = Purchase(
                        id=int(r.get("id")),
                        id_proveedor=int(r.get("tercero_id") or r.get("id_proveedor") or 0),
                        fecha_compra=r.get("fecha"),
                        total_compra=_to_val(r.get("total")) or 0,
                        estado=str(r.get("estado") or "Pendiente"),
                        numero_documento=str(r.get("doc_numero") or ""),
                        moneda=str(r.get("moneda") or ""),
                        tasa_cambio=_to_val(r.get("tasa_cambio")) if r.get("tasa_cambio") is not None else None,
                        unidad_negocio=str(r.get("unidad_negocio") or ""),
                        proporcionalidad=str(r.get("proporcionalidad") or ""),
                        stock_policy=str(r.get("stock_policy") or ""),
                        referencia=str(r.get("referencia") or ""),
                    )
                    sess.add(pur)
                elif tipo == "venta":
                    sale = Sale(
                        id=int(r.get("ov_id") or r.get("id")),
                        id_cliente=int(r.get("tercero_id") or 0),
                        fecha_venta=r.get("fecha"),
                        total_venta=_to_val(r.get("total")) or 0,
                        estado=str(r.get("estado") or "Confirmada"),
                    )
                    sess.add(sale)
                elif tipo == "recepcion":
                    rec = Reception(
                        id=int(r.get("id")),
                        id_compra=int(r.get("oc_id") or 0),
                        tipo_doc=str(r.get("doc_tipo") or ""),
                        numero_documento=str(r.get("doc_numero") or ""),
                        fecha=r.get("fecha"),
                    )
                    sess.add(rec)
            except Exception:
                pass

        # Snapshot de inventario: sobreescribe stock_actual
        inv = _read("inventario")
        if inv:
            for r in inv:
                try:
                    pid = int(r.get("id_producto"))
                    stk = int(r.get("stock_actual") or 0)
                    prod = sess.get(Product, pid)
                    if prod is not None:
                        prod.stock_actual = stk
                except Exception:
                    pass

        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        try:
            wb.close()
        except Exception:
            pass
