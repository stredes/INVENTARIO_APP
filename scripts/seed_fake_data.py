# scripts/seed_fake_data.py
# -*- coding: utf-8 -*-
"""
Seed de datos falsos para INVENTARIO_APP.

- Proveedores, Clientes, Productos
- Compras (+ detalles) coherentes por proveedor
- Ventas (+ detalles) con fechas recientes
- Limpieza segura del esquema respetando FKs
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path
import sys
from typing import List, Tuple

from faker import Faker
from sqlalchemy.orm import Session

# -------------------------------------------------------------------------
# Bootstrap de rutas
#  - IMPORTANTE: añadimos la RAÍZ del proyecto al sys.path
#    para que `from src.data...` funcione (no agregues ROOT/src).
# -------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]  # .../INVENTARIO_APP
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ahora estos imports funcionan correctamente:
from src.data.database import get_engine, get_session  # type: ignore
from src.data.models import (  # type: ignore
    Base,
    Supplier,
    Product,
    Customer,
    Purchase,
    PurchaseDetail,
    Sale,
    SaleDetail,
    StockEntry,
    StockExit,
)

# Faker configurado para español (Chile) y semilla reproducible
FAKER_LOCALE = "es_CL"
FAKER_SEED = int(str(Path.cwd()).__hash__() & 0xFFFF)
fake = Faker(FAKER_LOCALE)
Faker.seed(FAKER_SEED)


# =========================================================================
# Funciones utilitarias
# =========================================================================
def _random_recent_datetime(days_back: int = 90) -> datetime:
    """Fecha/hora aleatoria en los últimos 'days_back' días."""
    end = datetime.now()
    start = end - timedelta(days=days_back)
    delta = end - start
    rand_sec = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=rand_sec)


# =========================================================================
# SEED: Proveedores / Clientes / Productos
# =========================================================================
def seed_suppliers(session: Session, n: int = 10) -> List[Supplier]:
    """Crea n proveedores y los persiste."""
    proveedores: List[Supplier] = []
    for _ in range(n):
        prov = Supplier(
            razon_social=fake.company(),
            rut=f"FAKE-{fake.unique.random_int(10000000, 99999999)}",
            contacto=fake.name(),
            telefono=fake.phone_number(),
            email=fake.company_email(),
            direccion=fake.address(),
        )
        session.add(prov)
        proveedores.append(prov)
    session.commit()
    return proveedores


def seed_customers(session: Session, n: int = 15) -> List[Customer]:
    """Crea n clientes y los persiste."""
    clientes: List[Customer] = []
    for _ in range(n):
        cli = Customer(
            razon_social=fake.company(),
            rut=f"FAKE-{fake.unique.random_int(10000000, 99999999)}",
            contacto=fake.name(),
            telefono=fake.phone_number(),
            email=fake.email(),
            direccion=fake.address(),
        )
        session.add(cli)
        clientes.append(cli)
    session.commit()
    return clientes


def seed_products(session: Session, proveedores: List[Supplier], n: int = 20) -> List[Product]:
    """
    Crea n productos y asigna exactamente un proveedor a cada uno.
    Regla de precios:
      precio_venta = (precio_compra * 1.19) * margen (margen fijo = 1.3)
    """
    if not proveedores:
        raise ValueError("No hay proveedores para asignar a los productos.")

    # Helpers para SKU y EAN13 únicos
    used_skus: set[str] = set()
    used_barcodes: set[str] = set()

    def _unique_sku() -> str:
        while True:
            sku = f"SKU-{fake.unique.random_int(1000, 9999)}"
            if sku not in used_skus:
                used_skus.add(sku)
                return sku

    def _ean13_check_digit(code12: str) -> str:
        """Calcula dígito verificador EAN13 para 12 dígitos (string)."""
        s = [int(c) for c in code12]
        odd = sum(s[::2])
        even = sum(s[1::2]) * 3
        total = odd + even
        dv = (10 - (total % 10)) % 10
        return str(dv)

    def _unique_ean13() -> str:
        # Prefijo 780 (Chile) + 9 dígitos aleatorios
        while True:
            base12 = "780" + f"{random.randint(0, 999999999):09d}"
            code = base12 + _ean13_check_digit(base12)
            if code not in used_barcodes:
                used_barcodes.add(code)
                return code

    productos: List[Product] = []
    for _ in range(n):
        pc = round(random.uniform(500, 5000), 2)  # precio compra (neto)
        iva = pc * 0.19
        precio_con_iva = pc + iva
        margen = 1.3
        pv = round(precio_con_iva * margen, 2)

        prov = random.choice(proveedores)

        nombre = fake.word().capitalize()
        # Mezcla de rubros comunes (agrega variedad y legibilidad)
        if random.random() < 0.5:
            cat = random.choice(["Guantes", "Mascarilla", "Turbina", "Resina", "Fresa", "Irrigador", "Compresa", "Jeringa"])  # dominio clínico general
            nombre = f"{cat} {fake.color_name().split()[0]}"

        sku = _unique_sku()
        # Decidir si el producto tendrá código de barras (70%)
        has_barcode = random.random() < 0.7
        barcode_val = _unique_ean13() if has_barcode else None

        prod = Product(
            nombre=nombre,
            sku=sku,
            precio_compra=pc,
            precio_venta=pv,
            stock_actual=random.randint(0, 200),
            unidad_medida=random.choice(["unidad", "caja", "kg", "lt"]),
            id_proveedor=prov.id,  # vínculo con proveedor
            barcode=barcode_val,
        )
        session.add(prod)
        productos.append(prod)
    session.commit()
    return productos


# =========================================================================
# SEED: Compras (coherentes por proveedor)
# =========================================================================
def seed_purchases(session: Session, proveedores: List[Supplier], productos: List[Product], n: int = 10) -> None:
    """
    Crea n compras. Para cada compra se elige un proveedor y
    SOLO productos de ese proveedor. El precio_unitario se guarda con IVA.
    """
    for _ in range(n):
        prov = random.choice(proveedores)

        # Filtrar productos del proveedor elegido
        productos_del_prov = [p for p in productos if getattr(p, "id_proveedor", None) == prov.id]
        if not productos_del_prov:
            # Si el proveedor no tiene productos todavía, omitir esta compra
            continue

        items = random.sample(productos_del_prov, k=min(len(productos_del_prov), random.randint(1, 4)))
        total = 0.0

        purchase = Purchase(
            id_proveedor=prov.id,
            total_compra=0.0,
            estado=random.choice(["Pendiente", "Completada"]),
        )
        session.add(purchase)
        session.flush()  # asegurar purchase.id

        for prod in items:
            cantidad = random.randint(1, 10)
            precio_con_iva = round(float(prod.precio_compra or 0.0) * 1.19, 2)
            subtotal = round(cantidad * precio_con_iva, 2)
            total += subtotal

            detail = PurchaseDetail(
                id_compra=purchase.id,
                id_producto=prod.id,
                cantidad=cantidad,
                precio_unitario=precio_con_iva,  # almacenado con IVA
                subtotal=subtotal,
            )
            session.add(detail)

        purchase.total_compra = round(total, 2)
    session.commit()


# =========================================================================
# SEED: Ventas
# =========================================================================
def seed_sales(session: Session, clientes: List[Customer], productos: List[Product], n: int = 25) -> None:
    """
    Crea n ventas con 1..5 ítems cada una.
    Modelos esperados:
      - Sale:    id, fecha_venta(datetime), total_venta(float), estado(str), id_cliente(int) o customer_id
      - Detail:  id_venta, id_producto, cantidad, precio_unitario, subtotal
    """
    # Detectar nombre real de FK del cliente (id_cliente vs customer_id)
    sale_fk_name = "id_cliente"
    if hasattr(Sale, "customer_id"):
        sale_fk_name = "customer_id"

    estados = ["Confirmada", "Borrador", "Cancelada"]

    for _ in range(n):
        cust = random.choice(clientes)
        items = random.sample(productos, k=random.randint(1, 5))
        fecha = _random_recent_datetime(120)
        estado = random.choices(estados, weights=[0.6, 0.25, 0.15], k=1)[0]

        sale = Sale(
            fecha_venta=fecha,
            total_venta=0.0,  # se recalcula abajo
            estado=estado,
            **{sale_fk_name: cust.id},
        )
        session.add(sale)
        session.flush()  # obtener sale.id

        total = 0.0
        for prod in items:
            cantidad = random.randint(1, 8)
            base = float(prod.precio_venta or 0.0)
            price = round(base * random.uniform(0.9, 1.1), 2)  # ±10%
            subtotal = round(cantidad * price, 2)
            total += subtotal

            det = SaleDetail(
                id_venta=sale.id,
                id_producto=prod.id,
                cantidad=cantidad,
                precio_unitario=price,
                subtotal=subtotal,
            )
            session.add(det)

        sale.total_venta = round(total, 2)

    session.commit()


# =========================================================================
# Limpieza segura (ordenado por dependencias)
# =========================================================================
def clear_all(session: Session) -> None:
    """
    Limpia las tablas en un orden seguro respetando las claves foráneas.
    Si usas SQLite y tu engine no tiene PRAGMA FKs activado por defecto,
    este orden evita violaciones de integridad.
    """
    print("Eliminando datos previos (orden seguro por FKs)...")
    # Detalles primero
    session.query(SaleDetail).delete()
    session.query(Sale).delete()
    session.query(PurchaseDetail).delete()
    session.query(Purchase).delete()
    session.query(StockEntry).delete()
    session.query(StockExit).delete()
    # Entidades base al final
    session.query(Product).delete()
    session.query(Supplier).delete()
    session.query(Customer).delete()
    session.commit()


# =========================================================================
# MAIN
# =========================================================================
def main() -> None:
    engine = get_engine()
    # Crear tablas si no existen
    Base.metadata.create_all(engine)

    session: Session = get_session()
    try:
        clear_all(session)

        print("Generando datos falsos...")
        proveedores = seed_suppliers(session, 10)
        clientes = seed_customers(session, 15)
        productos = seed_products(session, proveedores, 20)

        seed_purchases(session, proveedores, productos, 10)
        seed_sales(session, clientes, productos, 25)

        print("¡Datos falsos insertados con éxito!")
    finally:
        session.close()


if __name__ == "__main__":
    # Recomendado ejecutarlo desde la RAÍZ del proyecto:
    #   python -m scripts.seed_fake_data
    # o bien:
    #   python .\scripts\seed_fake_data.py
    main()
