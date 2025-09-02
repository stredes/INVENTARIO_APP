from __future__ import annotations
from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import (
    Base,
    Product,
    Supplier,
    SupplierProduct,
    Purchase,
    PurchaseDetail,
    StockEntry,
    StockExit,
    Customer,
    Sale,
    SaleDetail,
)

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Repositorio base con CRUD simple."""
    def __init__(self, session: Session, model: Type[T]) -> None:
        self.session = session
        self.model = model

    def add(self, obj: T) -> T:
        self.session.add(obj)
        return obj

    def get(self, id_: int) -> Optional[T]:
        return self.session.get(self.model, id_)

    def list(self) -> List[T]:
        return list(self.session.query(self.model).all())

    def delete(self, id_: int) -> None:
        obj = self.get(id_)
        if obj:
            self.session.delete(obj)

    def query(self):
        return self.session.query(self.model)


# ---------------------------
# Products
# ---------------------------
class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Product)

    def get_by_sku(self, sku: str) -> Optional[Product]:
        """
        Busca por Código/SKU con comparación case-insensitive
        y sin espacios a la izquierda/derecha.
        """
        s = sku.strip()
        return (
            self.session.query(Product)
            .filter(func.lower(Product.sku) == func.lower(s))
            .first()
        )

    def exists_sku(self, sku: str) -> bool:
        return self.get_by_sku(sku) is not None

    def upsert_by_sku(self, sku: str, **fields) -> Product:
        """
        Crea o actualiza un producto por SKU (Código).
        Si existe, actualiza los campos provistos; si no, lo crea.
        No hace commit: permite transaccionar desde el caller.
        """
        s = sku.strip()
        p = self.get_by_sku(s)
        if p is None:
            p = Product(sku=s, **fields)
            self.session.add(p)
        else:
            for k, v in fields.items():
                setattr(p, k, v)
        self.session.flush()  # asegura p.id
        return p


# ---------------------------
# Suppliers / SupplierProduct
# ---------------------------
class SupplierRepository(BaseRepository[Supplier]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Supplier)


class SupplierProductRepository(BaseRepository[SupplierProduct]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, SupplierProduct)

    def link_supplier_product(self, supplier_id: int, product_id: int, precio: float) -> SupplierProduct:
        link = SupplierProduct(
            id_proveedor=supplier_id,
            id_producto=product_id,
            precio_proveedor=precio,
        )
        self.session.add(link)
        return link


# ---------------------------
# Purchases
# ---------------------------
class PurchaseRepository(BaseRepository[Purchase]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Purchase)


class PurchaseDetailRepository(BaseRepository[PurchaseDetail]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, PurchaseDetail)


# ---------------------------
# Stock Movements
# ---------------------------
class StockEntryRepository(BaseRepository[StockEntry]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, StockEntry)


class StockExitRepository(BaseRepository[StockExit]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, StockExit)


# ---------------------------
# Sales / Customers
# ---------------------------
class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Customer)


class SaleRepository(BaseRepository[Sale]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Sale)


class SaleDetailRepository(BaseRepository[SaleDetail]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, SaleDetail)
