# scripts/seed_fake_data.py
import sys
from pathlib import Path

# Ensure project root is on sys.path so `src` package resolves when run as a script.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from faker import Faker
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from src.data.database import get_engine, get_session
from src.data.models import (
    Base,
    Supplier,
    Product,
    Customer,
    Purchase,
    PurchaseDetail,
    # NUEVO: modelos de ventas
    Sale,
    SaleDetail,
    # NUEVO: movimientos de stock (para limpieza segura)
    StockEntry,
    StockExit,
)

fake = Faker("es_CL")  # Datos falsos en español de Chile


# -------------------------
# SEED FUNCTIONS
# -------------------------
def seed_suppliers(session: Session, n: int = 10):
    """Crea n proveedores."""
    proveedores = []
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


def seed_customers(session: Session, n: int = 15):
    """Crea n clientes."""
    clientes = []
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


def seed_products(session: Session, proveedores, n: int = 20):
    """
    Crea n productos y asigna **un proveedor** a cada uno (regla nueva).
    Calcula precio_venta como (precio_compra * 1.19) * margen.
    """
    if not proveedores:
        raise ValueError("No hay proveedores para asignar a los productos.")

    productos = []
    for _ in range(n):
        pc = round(random.uniform(500, 5000), 2)  # precio compra (neto)
        iva = pc * 0.19
        precio_con_iva = pc + iva
        margen = 1.3
        pv = round(precio_con_iva * margen, 2)

        prov = random.choice(proveedores)

        prod = Product(
            nombre=fake.word().capitalize(),
            sku=f"SKU-{fake.unique.random_int(1000, 9999)}",
            precio_compra=pc,
            precio_venta=pv,
            stock_actual=random.randint(0, 200),
            unidad_medida=random.choice(["unidad", "caja", "kg", "lt"]),
            id_proveedor=prov.id,  # **CLAVE**: vínculo a proveedor
        )
        session.add(prod)
        productos.append(prod)
    session.commit()
    return productos


def seed_purchases(session: Session, proveedores, productos, n: int = 10):
    """
    Crea n compras. Para cada compra selecciona un proveedor y
    **solo productos de ese proveedor**. El precio_unitario se guarda **con IVA**.
    """
    for _ in range(n):
        prov = random.choice(proveedores)

        # Filtrar productos del proveedor elegido
        productos_del_prov = [p for p in productos if getattr(p, "id_proveedor", None) == prov.id]
        if not productos_del_prov:
            # Si este proveedor no tiene productos, saltamos esta iteración
            continue

        items = random.sample(productos_del_prov, k=min(len(productos_del_prov), random.randint(1, 4)))
        total = 0.0

        purchase = Purchase(
            id_proveedor=prov.id,
            # puedes activar fecha_compra si tu modelo lo tiene:
            # fecha_compra=fake.date_time_between(start_date="-90d", end_date="now"),
            total_compra=0.0,
            estado=random.choice(["Pendiente", "Completada"]),
        )
        session.add(purchase)
        session.flush()  # asegura que tengamos purchase.id

        for prod in items:
            cantidad = random.randint(1, 10)
            precio_con_iva = round(float(prod.precio_compra or 0.0) * 1.19, 2)
            subtotal = round(cantidad * precio_con_iva, 2)
            total += subtotal
            detail = PurchaseDetail(
                id_compra=purchase.id,
                id_producto=prod.id,
                cantidad=cantidad,
                precio_unitario=precio_con_iva,  # **con IVA**
                subtotal=subtotal,
            )
            session.add(detail)

        purchase.total_compra = round(total, 2)
    session.commit()


# -------------------------
# NUEVO: Ventas
# -------------------------
def _random_recent_datetime(days_back: int = 90) -> datetime:
    """Fecha/hora aleatoria en los últimos 'days_back' días."""
    end = datetime.now()
    start = end - timedelta(days=days_back)
    delta = end - start
    rand_sec = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=rand_sec)


def seed_sales(session: Session, clientes, productos, n: int = 25):
    """
    Crea n ventas con 1..5 ítems cada una.
    Modelos esperados:
      - Sale:    id, fecha_venta(datetime), total_venta(float), estado(str), id_cliente(int) (o customer_id)
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
            total_venta=0.0,  # se recalcula
            estado=estado,
            **{sale_fk_name: cust.id},
        )
        session.add(sale)
        session.flush()  # obtener sale.id

        total = 0.0
        for prod in items:
            cantidad = random.randint(1, 8)
            # Precio de venta base, con un pequeño ajuste aleatorio ±10%
            base = float(prod.precio_venta or 0.0)
            price = round(base * random.uniform(0.9, 1.1), 2)
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


# -------------------------
# MAIN
# -------------------------
def main():
    engine = get_engine()
    Base.metadata.create_all(engine)
    session = get_session()

    # ⚠️ Limpiar tablas antes de insertar (orden seguro por FKs)
    print("Eliminando datos previos...")
    # Primero detalles/históricos que dependen de productos/compras/ventas
    session.query(SaleDetail).delete()
    session.query(Sale).delete()
    session.query(PurchaseDetail).delete()
    session.query(Purchase).delete()
    session.query(StockEntry).delete()
    session.query(StockExit).delete()
    # Luego entidades hijas antes que padres (Producto antes que Proveedor)
    session.query(Product).delete()
    session.query(Supplier).delete()
    session.query(Customer).delete()
    session.commit()

    # Insertar nuevos datos
    print("Generando datos falsos...")
    proveedores = seed_suppliers(session, 10)
    clientes = seed_customers(session, 15)
    productos = seed_products(session, proveedores, 20)

    seed_purchases(session, proveedores, productos, 10)
    # NUEVO: sembrar ventas
    seed_sales(session, clientes, productos, 25)

    print("¡Datos falsos insertados con éxito!")


if __name__ == "__main__":
    main()
