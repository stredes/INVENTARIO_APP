from __future__ import annotations

from typing import Optional, List
from decimal import Decimal
from datetime import datetime as dt

from sqlalchemy import (
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos."""
    pass


# ====================================================
# PROVEEDORES
# ====================================================
class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Razón social del proveedor (obligatoria)
    razon_social: Mapped[str] = mapped_column(String, nullable=False)

    # RUT de la empresa (único)
    rut: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    contacto: Mapped[Optional[str]] = mapped_column(String)
    telefono: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String)
    direccion: Mapped[Optional[str]] = mapped_column(String)

    # NUEVO: relación 1→N directa a productos (cada producto tiene 1 proveedor)
    products: Mapped[List["Product"]] = relationship(
        back_populates="supplier",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Supplier razon_social={self.razon_social} rut={self.rut}>"


# ====================================================
# PRODUCTOS
# ====================================================
class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("precio_compra >= 0", name="ck_products_precio_compra_nonneg"),
        CheckConstraint("precio_venta >= 0", name="ck_products_precio_venta_nonneg"),
        CheckConstraint("stock_actual >= 0", name="ck_products_stock_nonneg"),
        CheckConstraint("length(trim(sku)) > 0", name="ck_products_sku_not_empty"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    precio_compra: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    precio_venta: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stock_actual: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unidad_medida: Mapped[Optional[str]] = mapped_column(String)
    # Familia o categoría del producto (texto libre para filtros)
    familia: Mapped[Optional[str]] = mapped_column(String)

    # Ruta (absoluta o relativa) a la imagen principal del producto
    image_path: Mapped[Optional[str]] = mapped_column(String)
    # Código de barras opcional
    barcode: Mapped[Optional[str]] = mapped_column(String)

    # NUEVO: FK al proveedor (regla de negocio: obligatorio a nivel de app)
    id_proveedor: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    supplier: Mapped["Supplier"] = relationship(back_populates="products")

    # NUEVO: Ubicación (bodega/estantería) opcional
    id_ubicacion: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True)
    location: Mapped[Optional["Location"]] = relationship()

    def __repr__(self) -> str:
        return f"<Product id={self.id} sku={self.sku} nombre={self.nombre} prov={self.id_proveedor}>"


# ====================================================
# FAMILIAS (catálogo simple de nombres)
# ====================================================
class Family(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"<Family id={self.id} nombre={self.nombre}>"


# ====================================================
# PRODUCTOS DE PROVEEDORES (LEGACY - ya no se usa para el flujo nuevo)
# ====================================================
class SupplierProduct(Base):
    """
    LEGACY: Antes existía relación M:N producto↔proveedor con precio específico.
    Con proveedor único por producto, esta tabla queda obsoleta y debería
    eliminarse cuando completes la migración de datos.
    """
    __tablename__ = "supplier_products"
    __table_args__ = (
        UniqueConstraint("id_proveedor", "id_producto", name="uq_supplier_product"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_proveedor: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    id_producto: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    precio_proveedor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Sin back_populates para no interferir con la relación directa nueva
    supplier: Mapped["Supplier"] = relationship()
    product: Mapped["Product"] = relationship()

    def __repr__(self) -> str:
        return f"<SupplierProduct prov={self.id_proveedor} prod={self.id_producto}>"


# ====================================================
# UBICACIONES (Bodegas / Estanterías)
# ====================================================
class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    descripcion: Mapped[Optional[str]] = mapped_column(String)

    def __repr__(self) -> str:
        return f"<Location id={self.id} nombre={self.nombre}>"


# ====================================================
# COMPRAS
# ====================================================
class Purchase(Base):
    __tablename__ = "purchases"
    __table_args__ = (
        CheckConstraint("total_compra >= 0", name="ck_purchases_total_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_proveedor: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    fecha_compra: Mapped[dt] = mapped_column(DateTime, nullable=False, default=dt.utcnow)
    total_compra: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    estado: Mapped[str] = mapped_column(String, nullable=False)  # Pendiente/Completada/Cancelada

    # Campos adicionales de cabecera (opcionales)
    numero_documento: Mapped[Optional[str]] = mapped_column(String)
    fecha_documento: Mapped[Optional[dt]] = mapped_column(DateTime, nullable=True)
    fecha_contable: Mapped[Optional[dt]] = mapped_column(DateTime, nullable=True)
    fecha_vencimiento: Mapped[Optional[dt]] = mapped_column(DateTime, nullable=True)
    moneda: Mapped[Optional[str]] = mapped_column(String)
    tasa_cambio: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    unidad_negocio: Mapped[Optional[str]] = mapped_column(String)
    proporcionalidad: Mapped[Optional[str]] = mapped_column(String)
    atencion: Mapped[Optional[str]] = mapped_column(String)
    tipo_descuento: Mapped[Optional[str]] = mapped_column(String)  # 'Monto' | 'Porcentaje'
    descuento: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    ajuste_iva: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    stock_policy: Mapped[Optional[str]] = mapped_column(String)  # 'Mueve' | 'No Mueve'
    referencia: Mapped[Optional[str]] = mapped_column(String)
    ajuste_impuesto: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))

    supplier: Mapped["Supplier"] = relationship()
    details: Mapped[List["PurchaseDetail"]] = relationship(
        back_populates="purchase", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Purchase id={self.id} prov={self.id_proveedor} total={self.total_compra}>"


class PurchaseDetail(Base):
    __tablename__ = "purchase_details"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_purchase_details_qty_pos"),
        CheckConstraint("precio_unitario > 0", name="ck_purchase_details_price_pos"),
        CheckConstraint("subtotal >= 0", name="ck_purchase_details_subtotal_nonneg"),
        CheckConstraint("received_qty >= 0", name="ck_purchase_details_received_nonneg"),
        CheckConstraint("received_qty <= cantidad", name="ck_purchase_details_received_le_qty"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_compra: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False)
    id_producto: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    # Cantidad recepcionada acumulada para vincular OC con recepciones
    received_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    purchase: Mapped["Purchase"] = relationship(back_populates="details")
    product: Mapped["Product"] = relationship()

    def __repr__(self) -> str:
        return f"<PurchaseDetail compra={self.id_compra} prod={self.id_producto} cant={self.cantidad}>"


# ====================================================
# RECEPCIONES (vinculan OC con documento de proveedor)
# ====================================================
class Reception(Base):
    __tablename__ = "receptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_compra: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False)
    tipo_doc: Mapped[Optional[str]] = mapped_column(String)  # 'Factura' | 'Guía'
    numero_documento: Mapped[Optional[str]] = mapped_column(String)
    fecha: Mapped[dt] = mapped_column(DateTime, nullable=False, default=dt.utcnow)


# ====================================================
# MOVIMIENTOS DE STOCK
# ====================================================
class StockEntry(Base):
    __tablename__ = "stock_entries"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_stock_entries_qty_pos"),
        CheckConstraint("NOT (lote IS NOT NULL AND serie IS NOT NULL)", name="ck_stock_entries_lote_xor_serie"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_producto: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    # Ubicación donde entra el stock (opcional; puede diferir del default del producto)
    id_ubicacion: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True)
    # Recepción opcional a la que pertenece este ingreso
    id_recepcion: Mapped[Optional[int]] = mapped_column(ForeignKey("receptions.id"), nullable=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String)
    # Trazabilidad opcional: lote o serie (exclusivos) y vencimiento
    lote: Mapped[Optional[str]] = mapped_column(String)
    serie: Mapped[Optional[str]] = mapped_column(String)
    fecha_vencimiento: Mapped[Optional[dt]] = mapped_column(DateTime, nullable=True)
    fecha: Mapped[dt] = mapped_column(DateTime, nullable=False, default=dt.utcnow)

    product: Mapped["Product"] = relationship()
    location: Mapped[Optional["Location"]] = relationship()

    def __repr__(self) -> str:
        return f"<StockEntry prod={self.id_producto} +{self.cantidad} lote={getattr(self,'lote',None)} serie={getattr(self,'serie',None)}>"


class StockExit(Base):
    __tablename__ = "stock_exits"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_stock_exits_qty_pos"),
        CheckConstraint("NOT (lote IS NOT NULL AND serie IS NOT NULL)", name="ck_stock_exits_lote_xor_serie"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_producto: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    # Permitir identificar lote/serie y ubicación de la salida para multi-lote
    id_ubicacion: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String)
    # Opcional: enlazar salida a un lote/serie específico
    lote: Mapped[Optional[str]] = mapped_column(String)
    serie: Mapped[Optional[str]] = mapped_column(String)
    fecha: Mapped[dt] = mapped_column(DateTime, nullable=False, default=dt.utcnow)

    product: Mapped["Product"] = relationship()
    location: Mapped[Optional["Location"]] = relationship()

    def __repr__(self) -> str:
        return f"<StockExit prod={self.id_producto} -{self.cantidad} lote={getattr(self,'lote',None)} serie={getattr(self,'serie',None)}>"


# ====================================================
# CLIENTES
# ====================================================
class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Razón social del cliente
    razon_social: Mapped[str] = mapped_column(String, nullable=False)

    # RUT (único)
    rut: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    contacto: Mapped[Optional[str]] = mapped_column(String)
    telefono: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String)
    direccion: Mapped[Optional[str]] = mapped_column(String)

    sales: Mapped[List["Sale"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Customer razon_social={self.razon_social} rut={self.rut}>"


# ====================================================
# VENTAS
# ====================================================
class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("total_venta >= 0", name="ck_sales_total_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_cliente: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    fecha_venta: Mapped[dt] = mapped_column(DateTime, nullable=False, default=dt.utcnow)
    total_venta: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    estado: Mapped[str] = mapped_column(String, nullable=False)  # Borrador/Confirmada/Cancelada

    customer: Mapped["Customer"] = relationship(back_populates="sales")
    details: Mapped[List["SaleDetail"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Sale id={self.id} cliente={self.id_cliente} total={self.total_venta}>"


class SaleDetail(Base):
    __tablename__ = "sale_details"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_sale_details_qty_pos"),
        CheckConstraint("precio_unitario > 0", name="ck_sale_details_price_pos"),
        CheckConstraint("subtotal >= 0", name="ck_sale_details_subtotal_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_venta: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    id_producto: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    sale: Mapped["Sale"] = relationship(back_populates="details")
    product: Mapped["Product"] = relationship()

    def __repr__(self) -> str:
        return f"<SaleDetail venta={self.id_venta} prod={self.id_producto} cant={self.cantidad}>"

