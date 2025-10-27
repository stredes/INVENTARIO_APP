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
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    synonym,
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
    # Alias de compatibilidad: permitir usar 'nombre' en tests/código legado
    nombre = synonym("razon_social")

    # RUT de la empresa (único). En tests/semillas puede ser omitido -> permitir NULL
    rut: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    # Código de barras (EAN/UPC/etc). Opcional pero único si se define
    barcode: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    precio_compra: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    precio_venta: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stock_actual: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unidad_medida: Mapped[Optional[str]] = mapped_column(String)

    # Ruta (absoluta o relativa) a la imagen principal del producto
    image_path: Mapped[Optional[str]] = mapped_column(String)

    # FK al proveedor (permitimos NULL para compatibilidad con tests que crean sin proveedor)
    id_proveedor: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    supplier: Mapped["Supplier"] = relationship(back_populates="products")

    def __repr__(self) -> str:
        return f"<Product id={self.id} sku={self.sku} nombre={self.nombre} prov={self.id_proveedor}>"


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
# COMPRAS
# ====================================================
class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_proveedor: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    fecha_compra: Mapped[dt] = mapped_column(DateTime, nullable=False, default=dt.utcnow)
    total_compra: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    estado: Mapped[str] = mapped_column(String, nullable=False)  # Pendiente/Completada/Cancelada

    supplier: Mapped["Supplier"] = relationship()
    details: Mapped[List["PurchaseDetail"]] = relationship(
        back_populates="purchase", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Purchase id={self.id} prov={self.id_proveedor} total={self.total_compra}>"


class PurchaseDetail(Base):
    __tablename__ = "purchase_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_compra: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False)
    id_producto: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    purchase: Mapped["Purchase"] = relationship(back_populates="details")
    product: Mapped["Product"] = relationship()

    def __repr__(self) -> str:
        return f"<PurchaseDetail compra={self.id_compra} prod={self.id_producto} cant={self.cantidad}>"


# ====================================================
# MOVIMIENTOS DE STOCK
# ====================================================
class StockEntry(Base):
    __tablename__ = "stock_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_producto: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String)
    fecha: Mapped[dt] = mapped_column(DateTime, nullable=False, default=dt.utcnow)

    product: Mapped["Product"] = relationship()

    def __repr__(self) -> str:
        return f"<StockEntry prod={self.id_producto} +{self.cantidad}>"


class StockExit(Base):
    __tablename__ = "stock_exits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_producto: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String)
    fecha: Mapped[dt] = mapped_column(DateTime, nullable=False, default=dt.utcnow)

    product: Mapped["Product"] = relationship()

    def __repr__(self) -> str:
        return f"<StockExit prod={self.id_producto} -{self.cantidad}>"


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

