from __future__ import annotations

import sqlite3

from utils.paths import get_database_dir


DATA_DIR = get_database_dir()
DB_PATH = DATA_DIR / "facturion.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL,
                invoice_date TEXT NOT NULL,
                client TEXT NOT NULL,
                description TEXT,
                net_amount REAL NOT NULL,
                vat_rate REAL NOT NULL,
                vat_amount REAL NOT NULL,
                tag_amount REAL NOT NULL DEFAULT 0,
                accountant_amount REAL NOT NULL DEFAULT 0,
                savings_amount REAL NOT NULL DEFAULT 0,
                total_amount REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        invoice_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(invoices)").fetchall()
        }
        for column in (
            "deposit_amount",
            "savings_amount",
            "deposit_manuel_amount",
            "paid_vat_amount",
            "paid_accountant_amount",
            "paid_savings_amount",
            "paid_tag_amount",
        ):
            if column not in invoice_columns:
                cursor.execute(f"ALTER TABLE invoices ADD COLUMN {column} REAL NOT NULL DEFAULT 0")
        cursor.execute("DROP INDEX IF EXISTS idx_invoices_number_date")
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_invoices_number_date_lookup
            ON invoices(invoice_number, invoice_date)
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sii_reconciliations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL UNIQUE,
                sii_vat_amount REAL NOT NULL,
                actual_tag_paid REAL NOT NULL DEFAULT 0,
                actual_accountant_paid REAL NOT NULL DEFAULT 0,
                observation TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        existing_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(sii_reconciliations)").fetchall()
        }
        if "actual_tag_paid" not in existing_columns:
            cursor.execute(
                "ALTER TABLE sii_reconciliations ADD COLUMN actual_tag_paid REAL NOT NULL DEFAULT 0"
            )
        if "actual_accountant_paid" not in existing_columns:
            cursor.execute(
                "ALTER TABLE sii_reconciliations ADD COLUMN actual_accountant_paid REAL NOT NULL DEFAULT 0"
            )
        cursor.execute(
            """
            INSERT OR IGNORE INTO settings(key, value)
            VALUES ('vat_rate', '19')
            """
        )
        connection.commit()


def clear_operational_data() -> None:
    """
    Limpia los datos operativos de Facturion sin borrar configuración.

    Conserva:
    - tabla settings

    Elimina:
    - facturas
    - conciliaciones SII
    """
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM sii_reconciliations")
        cursor.execute("DELETE FROM invoices")
        connection.commit()
