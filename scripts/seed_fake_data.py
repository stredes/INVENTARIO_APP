# scripts/seed_fake_data.py
from faker import Faker
import random
from sqlalchemy.orm import Session

from src.data.database import get_engine, get_session
from src.data.models import (
    Base,
    Supplier,
    Product,
    Customer,
    Purchase,
    PurchaseDetail,
)

fake = Faker("es_CL")  # Datos falsos en español de Chile


# -------------------------
# SEED FUNCTIONS
# -------------------------
def seed_suppliers(session: Session, n=10):
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


def seed_customers(session: Session, n=15):
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


def seed_products(session: Session, n=20):
    productos = []
    for _ in range(n):
        pc = round(random.uniform(500, 5000), 2)
        iva = pc * 0.19
        precio_con_iva = pc + iva
        margen = 1.3
        pv = round(precio_con_iva * margen, 2)

        prod = Product(
            nombre=fake.word().capitalize(),
            sku=f"SKU-{fake.unique.random_int(1000, 9999)}",
            precio_compra=pc,
            precio_venta=pv,
            stock_actual=random.randint(0, 200),
            unidad_medida=random.choice(["unidad", "caja", "kg", "lt"]),
        )
        session.add(prod)
        productos.append(prod)
    session.commit()
    return productos


def seed_purchases(session: Session, proveedores, productos, n=10):
    for _ in range(n):
        prov = random.choice(proveedores)
        items = random.sample(productos, k=random.randint(1, 4))
        total = 0
        purchase = Purchase(
            id_proveedor=prov.id,
            total_compra=0,
            estado=random.choice(["Pendiente", "Completada"]),
        )
        session.add(purchase)
        session.flush()  # asegura que tengamos purchase.id

        for prod in items:
            cantidad = random.randint(1, 10)
            precio = prod.precio_compra
            subtotal = cantidad * precio
            total += subtotal
            detail = PurchaseDetail(
                id_compra=purchase.id,
                id_producto=prod.id,
                cantidad=cantidad,
                precio_unitario=precio,
                subtotal=subtotal,
            )
            session.add(detail)

        purchase.total_compra = total
    session.commit()


# -------------------------
# MAIN
# -------------------------
def main():
    engine = get_engine()
    Base.metadata.create_all(engine)
    session = get_session()

    # ⚠️ Limpiar tablas antes de insertar
    print("Eliminando datos previos...")
    session.query(PurchaseDetail).delete()
    session.query(Purchase).delete()
    session.query(Supplier).delete()
    session.query(Customer).delete()
    session.query(Product).delete()
    session.commit()

    # Insertar nuevos datos
    print("Generando datos falsos...")
    proveedores = seed_suppliers(session, 10)
    clientes = seed_customers(session, 15)
    productos = seed_products(session, 20)
    seed_purchases(session, proveedores, productos, 10)

    print("¡Datos falsos insertados con éxito!")


if __name__ == "__main__":
    main()
