from __future__ import annotations

from database.connection import get_connection


class SettingsService:
    @staticmethod
    def get_vat_rate() -> float:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key = 'vat_rate'"
            ).fetchone()
        return float(row["value"]) if row else 19.0

    @staticmethod
    def update_vat_rate(vat_rate: float) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO settings(key, value)
                VALUES ('vat_rate', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (str(vat_rate),),
            )
            connection.commit()
