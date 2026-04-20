from __future__ import annotations

from typing import Any

from database.connection import get_connection
from models.reconciliation import Reconciliation


class ReconciliationService:
    @staticmethod
    def upsert(reconciliation: Reconciliation) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO sii_reconciliations(
                    month,
                    sii_vat_amount,
                    actual_tag_paid,
                    actual_accountant_paid,
                    actual_savings_paid,
                    observation,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(month) DO UPDATE SET
                    sii_vat_amount = excluded.sii_vat_amount,
                    actual_tag_paid = excluded.actual_tag_paid,
                    actual_accountant_paid = excluded.actual_accountant_paid,
                    actual_savings_paid = excluded.actual_savings_paid,
                    observation = excluded.observation,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    reconciliation.month,
                    reconciliation.sii_vat_amount,
                    reconciliation.actual_tag_paid,
                    reconciliation.actual_accountant_paid,
                    reconciliation.actual_savings_paid,
                    reconciliation.observation,
                ),
            )
            connection.commit()

    @staticmethod
    def get_by_month(month: str) -> dict[str, Any] | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM sii_reconciliations WHERE month = ?",
                (month,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def list_all() -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM sii_reconciliations ORDER BY month DESC"
            ).fetchall()
        return [dict(row) for row in rows]
