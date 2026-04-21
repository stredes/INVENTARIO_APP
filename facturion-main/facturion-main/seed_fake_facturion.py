"""
Seed fake para Facturion.

Genera:
- facturas falsas en varios meses
- conciliaciones SII de ejemplo

Uso:
  python seed_fake_facturion.py
  python seed_fake_facturion.py --months 6 --per-month 4
  python seed_fake_facturion.py --months 12 --per-month 25 --payments-per-month 8
  python seed_fake_facturion.py --cleanup
"""

from __future__ import annotations

import argparse
import random
from datetime import date, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.connection import get_connection, initialize_database
from services.report_service import ReportService


CLIENTS = [
    "Amilab",
    "Insumopark",
    "Tamapal Spa",
    "Aseo Integral Ltda",
    "Servicios Norte Spa",
    "Comercial Higiene Sur",
]

DESCRIPTIONS = [
    "Servicio de transporte",
    "Servicio de mantencion",
    "Servicio administrativo",
    "Servicio operativo mensual",
    "Servicio de apoyo logistico",
    "Servicio tecnico especializado",
]


def first_day_of_month(d: date) -> date:
    return d.replace(day=1)


def shift_months(d: date, months: int) -> date:
    year = d.year
    month = d.month + months
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def cleanup() -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM sii_reconciliations")
        connection.execute("DELETE FROM invoices")
        connection.commit()


def seed_month(month_start: date, per_month: int, payments_per_month: int, vat_rate: float) -> tuple[int, int, str]:
    created_invoices = 0
    created_payments = 0
    month_key = month_start.strftime("%Y-%m")
    month_vat = 0.0
    month_tag = 0.0
    month_accountant = 0.0
    month_savings = 0.0
    month_manuel = 0.0

    with get_connection() as connection:
        base_number = int(month_start.strftime("%Y%m")) * 10_000

        for i in range(per_month):
            invoice_date = month_start + timedelta(days=min((i % 27) + 1, 27))
            invoice_number = str(base_number + i + 1)
            client = random.choice(CLIENTS)
            description = random.choice(DESCRIPTIONS)

            net_amount = float(random.randrange(50_000, 5_000_001, 5_000))
            tag_amount = float(random.choice([0, 10_000, 20_000, 30_000, 40_000, 50_000, 75_000]))
            accountant_amount = float(random.choice([0, 10_000, 15_000, 20_000, 25_000, 30_000, 50_000]))
            savings_amount = float(random.choice([0, 5_000, 10_000, 15_000, 20_000, 35_000, 50_000]))

            totals = ReportService.calculate_invoice_totals(
                net_amount=net_amount,
                vat_rate=vat_rate,
                tag_amount=tag_amount,
                accountant_amount=accountant_amount,
                savings_amount=savings_amount,
            )
            manuel_amount = ReportService.calculate_manuel_deposit(
                {
                    "net_amount": net_amount,
                    "vat_amount": totals["vat_amount"],
                    "tag_amount": tag_amount,
                    "accountant_amount": accountant_amount,
                    "savings_amount": savings_amount,
                }
            )

            connection.execute(
                """
                INSERT INTO invoices(
                    invoice_number, invoice_date, client, description,
                    net_amount, vat_rate, vat_amount, tag_amount,
                    accountant_amount, savings_amount, total_amount,
                    deposit_manuel_amount, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    invoice_number,
                    invoice_date.strftime("%Y-%m-%d"),
                    client,
                    description,
                    net_amount,
                    vat_rate,
                    totals["vat_amount"],
                    tag_amount,
                    accountant_amount,
                    savings_amount,
                    totals["total_amount"],
                    manuel_amount,
                ),
            )
            created_invoices += 1
            month_vat += totals["vat_amount"]
            month_tag += tag_amount
            month_accountant += accountant_amount
            month_savings += savings_amount
            month_manuel += manuel_amount

        payment_plan = [
            ("sii_vat_amount", month_vat),
            ("actual_tag_paid", month_tag),
            ("actual_accountant_paid", month_accountant),
            ("actual_savings_paid", month_savings),
            ("actual_manuel_paid", month_manuel),
        ]

        for i in range(payments_per_month):
            values = {key: 0.0 for key, _amount in payment_plan}
            for key, amount in payment_plan:
                if amount <= 0:
                    continue
                target = amount / max(payments_per_month, 1)
                variation = random.uniform(0.65, 1.25)
                values[key] = float(round(max(0, target * variation)))
            observation = f"Pago fake {i + 1}/{payments_per_month} {month_key}"
            connection.execute(
                """
                INSERT INTO sii_reconciliations(
                    month, sii_vat_amount, actual_tag_paid, actual_accountant_paid,
                    actual_savings_paid, actual_manuel_paid, observation, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    month_key,
                    values["sii_vat_amount"],
                    values["actual_tag_paid"],
                    values["actual_accountant_paid"],
                    values["actual_savings_paid"],
                    values["actual_manuel_paid"],
                    observation,
                ),
            )
            created_payments += 1
        connection.commit()

    return created_invoices, created_payments, month_key


def read_vat_rate() -> float:
    with get_connection() as connection:
        row = connection.execute("SELECT value FROM settings WHERE key = 'vat_rate'").fetchone()
    try:
        return float(row["value"]) if row else 19.0
    except Exception:
        return 19.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed fake para Facturion")
    parser.add_argument("--months", type=int, default=4, help="Cantidad de meses a poblar")
    parser.add_argument("--per-month", type=int, default=3, help="Facturas por mes")
    parser.add_argument("--payments-per-month", type=int, default=3, help="Pagos por mes")
    parser.add_argument("--seed", type=int, default=None, help="Semilla random para repetir una prueba")
    parser.add_argument("--cleanup", action="store_true", help="Borra facturas/conciliaciones antes de insertar")
    args = parser.parse_args()

    initialize_database()
    if args.seed is not None:
        random.seed(args.seed)
    if args.cleanup:
        cleanup()

    vat_rate = read_vat_rate()
    today = first_day_of_month(date.today())
    total_invoices = 0
    total_payments = 0
    touched_months: list[str] = []

    for offset in range(args.months - 1, -1, -1):
        month_start = shift_months(today, -offset)
        invoices, payments, month_key = seed_month(
            month_start,
            args.per_month,
            args.payments_per_month,
            vat_rate,
        )
        total_invoices += invoices
        total_payments += payments
        touched_months.append(month_key)

    print(f"Facturas fake creadas: {total_invoices}")
    print(f"Pagos fake creados: {total_payments}")
    print(f"Meses afectados: {', '.join(touched_months)}")
    print("Seed Facturion finalizado.")


if __name__ == "__main__":
    main()
