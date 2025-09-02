from __future__ import annotations

from typing import Optional, List
from datetime import datetime as dt

from sqlalchemy import (
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
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
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    contacto: Mapped[Optional[str]] = mapped_column(String)
    telefono: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String)
    direccion: Mapped[Optional[str]] = mapped_column(String)

    products: Mapped[List["SupplierProduct"]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Supplier nombre={self.nombre}>"


# ====================================================
# PRODUCTOS
# ====================================================
class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    precio_compra: Mapped[float] = mapped_column(Float, nullable=False)
    precio_venta: Mapped[float] = mapped_column(Float, nullable=False)
    stock_actual: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unidad_medida: Mapped[Optional[str]] = mapped_column(String)

    def __repr__(self) -> str:
        return f"<Product sku={self.sku} nombre={self.nombre}>"


# ====================================================
# PRODUCTOS DE PROVEEDORES (PRECIOS ASOCIADOS)
# ====================================================
class SupplierProduct(Base):
    __tablename__ = "supplier_products"
    __table_args__ = (
        UniqueConstraint("id_proveedor", "id_producto", name="uq_supplier_product"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_proveedor: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    id_producto: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    precio_proveedor: Mapped[float] = mapped_column(Float, nullable=False)

    supplier: Mapped["Supplier"] = relationship(back_populates="products")
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
    total_compra: Mapped[float] = mapped_column(Float, nullable=False)
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
    precio_unitario: Mapped[float] = mapped_column(Float, nullable=False)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)

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
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    contacto: Mapped[Optional[str]] = mapped_column(String)
    telefono: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String)
    direccion: Mapped[Optional[str]] = mapped_column(String)

    sales: Mapped[List["Sale"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Customer nombre={self.nombre}>"


# ====================================================
# VENTAS
# ====================================================
class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_cliente: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    fecha_venta: Mapped[dt] = mapped_column(DateTime, nullable=False, default=dt.utcnow)
    total_venta: Mapped[float] = mapped_column(Float, nullable=False)
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
    precio_unitario: Mapped[float] = mapped_column(Float, nullable=False)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)

    sale: Mapped["Sale"] = relationship(back_populates="details")
    product: Mapped["Product"] = relationship()

    def __repr__(self) -> str:
        return f"<SaleDetail venta={self.id_venta} prod={self.id_producto} cant={self.cantidad}>"
