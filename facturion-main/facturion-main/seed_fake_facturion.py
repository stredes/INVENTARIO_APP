"""
Seed fake para Facturion.

Genera:
- facturas falsas en varios meses
- conciliaciones SII de ejemplo

Uso:
  python seed_fake_facturion.py
  python seed_fake_facturion.py --months 6 --per-month 4
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


def seed_month(month_start: date, per_month: int, vat_rate: float) -> tuple[int, str]:
    created = 0
    month_key = month_start.strftime("%Y-%m")
    month_net = 0.0
    month_vat = 0.0
    month_tag = 0.0
    month_accountant = 0.0

    with get_connection() as connection:
        base_number = int(month_start.strftime("%Y%m")) * 100

        for i in range(per_month):
            invoice_date = month_start + timedelta(days=min(i * 5 + 1, 27))
            invoice_number = str(base_number + i + 1)
            client = random.choice(CLIENTS)
            description = random.choice(DESCRIPTIONS)

            net_amount = float(random.randrange(180_000, 2_400_001, 10_000))
            tag_amount = float(random.choice([0, 10_000, 20_000, 30_000, 40_000]))
            accountant_amount = float(random.choice([0, 15_000, 20_000, 25_000, 30_000]))

            totals = ReportService.calculate_invoice_totals(
                net_amount=net_amount,
                vat_rate=vat_rate,
                tag_amount=tag_amount,
                accountant_amount=accountant_amount,
            )

            connection.execute(
                """
                INSERT INTO invoices(
                    invoice_number, invoice_date, client, description,
                    net_amount, vat_rate, vat_amount, tag_amount,
                    accountant_amount, total_amount, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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
                    totals["total_amount"],
                ),
            )
            created += 1
            month_net += net_amount
            month_vat += totals["vat_amount"]
            month_tag += tag_amount
            month_accountant += accountant_amount

        sii_vat_amount = float(round(max(0, month_vat - random.choice([0, 20_000, 40_000, 60_000]))))
        actual_tag_paid = float(round(max(0, month_tag - random.choice([0, 10_000, 20_000]))))
        actual_accountant_paid = float(round(max(0, month_accountant - random.choice([0, 10_000, 20_000]))))
        observation = f"Conciliacion fake {month_key}"

        connection.execute(
            """
            INSERT INTO sii_reconciliations(
                month, sii_vat_amount, actual_tag_paid, actual_accountant_paid, observation, updated_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(month) DO UPDATE SET
                sii_vat_amount = excluded.sii_vat_amount,
                actual_tag_paid = excluded.actual_tag_paid,
                actual_accountant_paid = excluded.actual_accountant_paid,
                observation = excluded.observation,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                month_key,
                sii_vat_amount,
                actual_tag_paid,
                actual_accountant_paid,
                observation,
            ),
        )
        connection.commit()

    return created, month_key


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
    parser.add_argument("--cleanup", action="store_true", help="Borra facturas/conciliaciones antes de insertar")
    args = parser.parse_args()

    initialize_database()
    if args.cleanup:
        cleanup()

    vat_rate = read_vat_rate()
    today = first_day_of_month(date.today())
    total_created = 0
    touched_months: list[str] = []

    for offset in range(args.months - 1, -1, -1):
        month_start = shift_months(today, -offset)
        created, month_key = seed_month(month_start, args.per_month, vat_rate)
        total_created += created
        touched_months.append(month_key)

    print(f"Facturas fake creadas: {total_created}")
    print(f"Meses afectados: {', '.join(touched_months)}")
    print("Seed Facturion finalizado.")


if __name__ == "__main__":
    main()
