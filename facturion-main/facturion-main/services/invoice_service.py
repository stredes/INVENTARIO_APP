from __future__ import annotations

from typing import Any

from database.connection import get_connection
from models.invoice import Invoice


class InvoiceService:
    @staticmethod
    def create(invoice: Invoice) -> int:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO invoices(
                    invoice_number, invoice_date, client, description,
                    net_amount, vat_rate, vat_amount, tag_amount,
                    accountant_amount, savings_amount, total_amount, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    invoice.invoice_number,
                    invoice.invoice_date,
                    invoice.client,
                    invoice.description,
                    invoice.net_amount,
                    invoice.vat_rate,
                    invoice.vat_amount,
                    invoice.tag_amount,
                    invoice.accountant_amount,
                    invoice.savings_amount,
                    invoice.total_amount,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    @staticmethod
    def update(invoice_id: int, invoice: Invoice) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE invoices
                SET invoice_number = ?,
                    invoice_date = ?,
                    client = ?,
                    description = ?,
                    net_amount = ?,
                    vat_rate = ?,
                    vat_amount = ?,
                    tag_amount = ?,
                    accountant_amount = ?,
                    savings_amount = ?,
                    total_amount = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    invoice.invoice_number,
                    invoice.invoice_date,
                    invoice.client,
                    invoice.description,
                    invoice.net_amount,
                    invoice.vat_rate,
                    invoice.vat_amount,
                    invoice.tag_amount,
                    invoice.accountant_amount,
                    invoice.savings_amount,
                    invoice.total_amount,
                    invoice_id,
                ),
            )
            connection.commit()

    @staticmethod
    def delete(invoice_id: int) -> None:
        with get_connection() as connection:
            connection.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
            connection.commit()

    @staticmethod
    def get(invoice_id: int) -> dict[str, Any] | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM invoices WHERE id = ?",
                (invoice_id,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def list_all(
        search: str = "",
        month: str = "",
        year: str = "",
    ) -> list[dict[str, Any]]:
        query = """
            SELECT *
            FROM invoices
            WHERE 1 = 1
        """
        params: list[Any] = []

        if search:
            query += """
                AND (
                    invoice_number LIKE ?
                    OR client LIKE ?
                    OR invoice_date LIKE ?
                )
            """
            search_value = f"%{search.strip()}%"
            params.extend([search_value, search_value, search_value])

        if month:
            query += " AND strftime('%m', invoice_date) = ?"
            params.append(f"{int(month):02d}")

        if year:
            query += " AND strftime('%Y', invoice_date) = ?"
            params.append(str(year))

        query += " ORDER BY invoice_date DESC, invoice_number DESC"

        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def exists_duplicate(invoice_number: str, invoice_date: str, exclude_id: int | None = None) -> bool:
        query = """
            SELECT id
            FROM invoices
            WHERE invoice_number = ? AND invoice_date = ?
        """
        params: list[Any] = [invoice_number, invoice_date]
        if exclude_id is not None:
            query += " AND id <> ?"
            params.append(exclude_id)

        with get_connection() as connection:
            row = connection.execute(query, params).fetchone()
        return row is not None
