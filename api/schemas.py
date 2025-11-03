from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field


# ---------- Generic ----------

class Message(BaseModel):
  message: str


# ---------- Suppliers ----------

class SupplierIn(BaseModel):
  razon_social: str
  rut: str
  contacto: Optional[str] = None
  telefono: Optional[str] = None
  email: Optional[str] = None
  direccion: Optional[str] = None


class SupplierOut(SupplierIn):
  id: int

  class Config:
    from_attributes = True


# ---------- Customers ----------

class CustomerIn(BaseModel):
  razon_social: str
  rut: str
  contacto: Optional[str] = None
  telefono: Optional[str] = None
  email: Optional[str] = None
  direccion: Optional[str] = None


class CustomerOut(CustomerIn):
  id: int

  class Config:
    from_attributes = True


# ---------- Products ----------

class ProductIn(BaseModel):
  nombre: str
  sku: str
  precio_compra: Decimal
  precio_venta: Decimal
  stock_actual: int = 0
  unidad_medida: Optional[str] = None
  familia: Optional[str] = None
  image_path: Optional[str] = None
  barcode: Optional[str] = None
  id_proveedor: int
  id_ubicacion: Optional[int] = None


class ProductOut(ProductIn):
  id: int

  class Config:
    from_attributes = True


class ProductLiteOut(BaseModel):
  id: int
  nombre: str
  sku: str

  class Config:
    from_attributes = True


# ---------- Inventory Movements ----------

class StockEntryIn(BaseModel):
  product_id: int
  cantidad: int = Field(gt=0)
  motivo: Optional[str] = None
  when: Optional[datetime] = None
  lote: Optional[str] = None
  serie: Optional[str] = None
  fecha_vencimiento: Optional[datetime] = None
  reception_id: Optional[int] = None
  location_id: Optional[int] = None


class StockExitIn(BaseModel):
  product_id: int
  cantidad: int = Field(gt=0)
  motivo: Optional[str] = None
  when: Optional[datetime] = None


# ---------- Purchases ----------

class PurchaseItemIn(BaseModel):
  product_id: int
  cantidad: int = Field(gt=0)
  precio_unitario: Decimal


class PurchaseCreate(BaseModel):
  supplier_id: int
  items: List[PurchaseItemIn]
  fecha: Optional[datetime] = None
  estado: str = "Completada"
  apply_to_stock: bool = True


class PurchaseOut(BaseModel):
  id: int
  id_proveedor: int
  fecha_compra: datetime
  total_compra: Decimal
  estado: str

  class Config:
    from_attributes = True


class PurchaseUpdate(BaseModel):
  # Cabecera y metadatos (todos opcionales para PATCH/PUT flexible)
  numero_documento: str | None = None
  fecha_documento: datetime | None = None
  fecha_contable: datetime | None = None
  fecha_vencimiento: datetime | None = None
  moneda: str | None = None
  tasa_cambio: Decimal | None = None
  unidad_negocio: str | None = None
  proporcionalidad: str | None = None
  atencion: str | None = None
  tipo_descuento: str | None = None  # 'Monto' | 'Porcentaje'
  descuento: Decimal | None = None
  ajuste_iva: Decimal | None = None
  stock_policy: str | None = None   # 'Mueve' | 'No Mueve'
  referencia: str | None = None
  ajuste_impuesto: Decimal | None = None
  estado: str | None = None


# ---------- Sales ----------

class SaleItemIn(BaseModel):
  product_id: int
  cantidad: int = Field(gt=0)
  precio_unitario: Decimal


class SaleCreate(BaseModel):
  customer_id: int
  items: List[SaleItemIn]
  fecha: Optional[datetime] = None
  estado: str = "Confirmada"
  apply_to_stock: bool = True


class SaleOut(BaseModel):
  id: int
  id_cliente: int
  fecha_venta: datetime
  total_venta: Decimal
  estado: str

  class Config:
    from_attributes = True


class SaleUpdate(BaseModel):
  estado: str | None = None
  fecha_venta: datetime | None = None


# ---------- Details for nested views ----------

class PurchaseDetailOut(BaseModel):
  id: int
  id_compra: int
  id_producto: int
  cantidad: int
  received_qty: int
  precio_unitario: Decimal
  subtotal: Decimal
  product: ProductLiteOut | None = None

  class Config:
    from_attributes = True


class SaleDetailOut(BaseModel):
  id: int
  id_venta: int
  id_producto: int
  cantidad: int
  precio_unitario: Decimal
  subtotal: Decimal
  product: ProductLiteOut | None = None

  class Config:
    from_attributes = True


class PurchaseWithDetails(PurchaseOut):
  details: list[PurchaseDetailOut]


class SaleWithDetails(SaleOut):
  details: list[SaleDetailOut]


# ---------- Locations ----------

class LocationIn(BaseModel):
  nombre: str
  descripcion: Optional[str] = None


class LocationOut(LocationIn):
  id: int

  class Config:
    from_attributes = True


# ---------- Reports ----------

class SalesReportItem(BaseModel):
  id: int
  fecha_venta: datetime
  cliente: str
  estado: str
  total_venta: Decimal


# ---------- Inventory ----------

class InventoryItemOut(BaseModel):
  id: int
  nombre: str
  sku: str
  stock_actual: int
  id_proveedor: int
  id_ubicacion: int | None = None
  familia: str | None = None
  min_threshold: int | None = None
  max_threshold: int | None = None
  below_min: bool | None = None

  class Config:
    from_attributes = True


class ThresholdIn(BaseModel):
  min_value: int
  max_value: int


class ThresholdOut(BaseModel):
  product_id: int
  min_value: int
  max_value: int


# ---------- Quote (Cotización) ----------

class QuoteSupplierIn(BaseModel):
  nombre: str | None = None
  contacto: str | None = None
  telefono: str | None = None
  direccion: str | None = None
  pago: str | None = None
  rut: str | None = None


class QuoteItemIn(BaseModel):
  id: int | None = None
  nombre: str
  unidad: str | None = "U"
  cantidad: Decimal
  precio: Decimal  # con IVA
  dcto: Decimal | None = None
  subtotal: Decimal | None = None


class QuoteCreate(BaseModel):
  quote_number: str
  supplier: QuoteSupplierIn
  items: list[QuoteItemIn]
  currency: str = "CLP"
  notes: str | None = None


# ---------- Receptions (Recepciones) ----------

class ReceptionItemIn(BaseModel):
  product_id: int
  received_qty: int
  id_ubicacion: int | None = None
  lote: str | None = None
  serie: str | None = None
  fecha_vencimiento: datetime | None = None


class ReceptionCreate(BaseModel):
  purchase_id: int
  tipo_doc: str | None = None
  numero_documento: str | None = None
  fecha: datetime | None = None
  items: list[ReceptionItemIn]
  apply_to_stock: bool = True
  update_status: bool = True


class ReceptionOut(BaseModel):
  id: int
  id_compra: int
  tipo_doc: str | None
  numero_documento: str | None
  fecha: datetime

  class Config:
    from_attributes = True
