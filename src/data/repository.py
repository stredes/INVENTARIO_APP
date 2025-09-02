from __future__ import annotations
from typing import Generic, List, Optional, Sequence, Type, TypeVar

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
    def __init__(self, session: Session, model: Type[T]) -> None:
        self.session = session
        self.model = model

    def add(self, obj: T) -> T:
        self.session.add(obj)
        return obj

    def get(self, id_: int) -> Optional[T]:
        return self.session.get(self.model, id_)

    def list(self) -> Sequence[T]:
        return self.session.query(self.model).all()

    def delete(self, id_: int) -> None:
        obj = self.get(id_)
        if obj:
            self.session.delete(obj)

    def query(self):
        return self.session.query(self.model)


class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Product)

    def get_by_sku(self, sku: str) -> Optional[Product]:
        return self.session.query(Product).filter(Product.sku == sku).first()


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


class PurchaseRepository(BaseRepository[Purchase]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Purchase)


class PurchaseDetailRepository(BaseRepository[PurchaseDetail]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, PurchaseDetail)


class StockEntryRepository(BaseRepository[StockEntry]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, StockEntry)


class StockExitRepository(BaseRepository[StockExit]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, StockExit)


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Customer)


class SaleRepository(BaseRepository[Sale]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Sale)


class SaleDetailRepository(BaseRepository[SaleDetail]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, SaleDetail)
