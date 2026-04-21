from __future__ import annotations

from typing import Any

from database.connection import get_connection
from models.reconciliation import Reconciliation


class ReconciliationService:
    @staticmethod
    def create(reconciliation: Reconciliation) -> int:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO sii_reconciliations(
                    month,
                    sii_vat_amount,
                    actual_tag_paid,
                    actual_accountant_paid,
                    actual_savings_paid,
                    actual_manuel_paid,
                    observation,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    reconciliation.month,
                    reconciliation.sii_vat_amount,
                    reconciliation.actual_tag_paid,
                    reconciliation.actual_accountant_paid,
                    reconciliation.actual_savings_paid,
                    reconciliation.actual_manuel_paid,
                    reconciliation.observation,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    @staticmethod
    def update(payment_id: int, reconciliation: Reconciliation) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE sii_reconciliations
                SET month = ?,
                    sii_vat_amount = ?,
                    actual_tag_paid = ?,
                    actual_accountant_paid = ?,
                    actual_savings_paid = ?,
                    actual_manuel_paid = ?,
                    observation = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    reconciliation.month,
                    reconciliation.sii_vat_amount,
                    reconciliation.actual_tag_paid,
                    reconciliation.actual_accountant_paid,
                    reconciliation.actual_savings_paid,
                    reconciliation.actual_manuel_paid,
                    reconciliation.observation,
                    payment_id,
                ),
            )
            connection.commit()

    @staticmethod
    def upsert(reconciliation: Reconciliation) -> None:
        if reconciliation.id is not None:
            ReconciliationService.update(reconciliation.id, reconciliation)
            return
        ReconciliationService.create(reconciliation)

    @staticmethod
    def get(payment_id: int) -> dict[str, Any] | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM sii_reconciliations WHERE id = ?",
                (payment_id,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_month(month: str) -> dict[str, Any] | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    month,
                    SUM(sii_vat_amount) AS sii_vat_amount,
                    SUM(actual_tag_paid) AS actual_tag_paid,
                    SUM(actual_accountant_paid) AS actual_accountant_paid,
                    SUM(actual_savings_paid) AS actual_savings_paid,
                    SUM(actual_manuel_paid) AS actual_manuel_paid,
                    GROUP_CONCAT(NULLIF(observation, ''), ' | ') AS observation
                FROM sii_reconciliations
                WHERE month = ?
                GROUP BY month
                """,
                (month,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def delete_by_month(month: str) -> bool:
        with get_connection() as connection:
            cursor = connection.execute(
                "DELETE FROM sii_reconciliations WHERE month = ?",
                (month,),
            )
            connection.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete(payment_id: int) -> bool:
        with get_connection() as connection:
            cursor = connection.execute(
                "DELETE FROM sii_reconciliations WHERE id = ?",
                (payment_id,),
            )
            connection.commit()
            return cursor.rowcount > 0

    @staticmethod
    def list_all() -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM sii_reconciliations ORDER BY month DESC, id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def list_monthly_totals() -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    month,
                    SUM(sii_vat_amount) AS sii_vat_amount,
                    SUM(actual_tag_paid) AS actual_tag_paid,
                    SUM(actual_accountant_paid) AS actual_accountant_paid,
                    SUM(actual_savings_paid) AS actual_savings_paid,
                    SUM(actual_manuel_paid) AS actual_manuel_paid,
                    GROUP_CONCAT(NULLIF(observation, ''), ' | ') AS observation
                FROM sii_reconciliations
                GROUP BY month
                ORDER BY month DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]
