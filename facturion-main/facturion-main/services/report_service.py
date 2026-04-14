from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from services.invoice_service import InvoiceService
from services.reconciliation_service import ReconciliationService


class ReportService:
    @staticmethod
    def calculate_invoice_totals(
        net_amount: float,
        vat_rate: float,
        tag_amount: float,
        accountant_amount: float,
    ) -> dict[str, float]:
        vat_amount = round(net_amount * (vat_rate / 100), 2)
        total_amount = round(net_amount + vat_amount + tag_amount + accountant_amount, 2)
        return {"vat_amount": vat_amount, "total_amount": total_amount}

    @staticmethod
    def monthly_summary(month: str, year: str) -> dict[str, Any]:
        month_key = f"{year}-{int(month):02d}"
        all_months = ReportService._build_monthly_balances(include_month=month_key)
        return all_months[month_key]

    @staticmethod
    def current_month_summary() -> dict[str, Any]:
        today = datetime.today()
        return ReportService.monthly_summary(str(today.month), str(today.year))

    @staticmethod
    def grouped_history() -> list[dict[str, Any]]:
        balanced_months = ReportService._build_monthly_balances()
        return sorted(balanced_months.values(), key=lambda item: item["month"], reverse=True)

    @staticmethod
    def _build_monthly_balances(include_month: str | None = None) -> dict[str, dict[str, Any]]:
        invoices = InvoiceService.list_all()
        grouped: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "month": "",
                "count": 0,
                "net_amount": 0.0,
                "vat_amount": 0.0,
                "tag_amount": 0.0,
                "accountant_amount": 0.0,
                "total_amount": 0.0,
            }
        )
        reconciliations = {item["month"]: item for item in ReconciliationService.list_all()}

        for invoice in invoices:
            month_key = invoice["invoice_date"][:7]
            entry = grouped[month_key]
            entry["month"] = month_key
            entry["count"] += 1
            entry["net_amount"] += invoice["net_amount"]
            entry["vat_amount"] += invoice["vat_amount"]
            entry["tag_amount"] += invoice["tag_amount"]
            entry["accountant_amount"] += invoice["accountant_amount"]
            entry["total_amount"] += invoice["total_amount"]

        all_months = set(grouped.keys()) | set(reconciliations.keys())
        if include_month:
            all_months.add(include_month)

        balanced: dict[str, dict[str, Any]] = {}
        previous_closing_balance = 0.0

        for month_key in sorted(all_months):
            entry = grouped.get(month_key, {}).copy() or {
                "month": month_key,
                "count": 0,
                "net_amount": 0.0,
                "vat_amount": 0.0,
                "tag_amount": 0.0,
                "accountant_amount": 0.0,
                "total_amount": 0.0,
            }
            for key in ("net_amount", "vat_amount", "tag_amount", "accountant_amount", "total_amount"):
                entry[key] = round(entry[key], 2)

            reconciliation = reconciliations.get(month_key)
            sii_vat = reconciliation["sii_vat_amount"] if reconciliation else 0.0
            actual_tag_paid = reconciliation["actual_tag_paid"] if reconciliation else 0.0
            actual_accountant_paid = reconciliation["actual_accountant_paid"] if reconciliation else 0.0
            tax_balance = round(entry["vat_amount"] - sii_vat, 2)
            tag_balance = round(entry["tag_amount"] - actual_tag_paid, 2)
            accountant_balance = round(entry["accountant_amount"] - actual_accountant_paid, 2)
            charges_total = round(tag_balance + accountant_balance, 2)
            opening_balance = round(previous_closing_balance, 2)
            closing_balance = round(opening_balance + tax_balance + charges_total, 2)

            entry["sii_vat_amount"] = sii_vat
            entry["actual_tag_paid"] = round(actual_tag_paid, 2)
            entry["actual_accountant_paid"] = round(actual_accountant_paid, 2)
            entry["tax_balance"] = tax_balance
            entry["tag_balance"] = tag_balance
            entry["accountant_balance"] = accountant_balance
            entry["charges_total"] = charges_total
            entry["opening_balance"] = opening_balance
            entry["balance"] = closing_balance
            entry["balance_status"] = ReportService.balance_status(closing_balance, reconciliation is not None)
            entry["observation"] = reconciliation["observation"] if reconciliation else ""
            entry["balance_message"] = ReportService.balance_message(
                closing_balance,
                reconciliation is not None,
                opening_balance,
                tax_balance,
                tag_balance,
                accountant_balance,
            )

            balanced[month_key] = entry
            previous_closing_balance = closing_balance

        return balanced

    @staticmethod
    def balance_status(balance: float, has_reconciliation: bool) -> str:
        if not has_reconciliation:
            return "Pendiente SII"
        if balance > 0:
            return "A favor"
        if balance < 0:
            return "En contra"
        return "Sin diferencia"

    @staticmethod
    def balance_message(
        balance: float,
        has_reconciliation: bool,
        opening_balance: float,
        tax_balance: float,
        tag_balance: float,
        accountant_balance: float,
    ) -> str:
        charges_total = round(tag_balance + accountant_balance, 2)
        if not has_reconciliation:
            return (
                "Aun no se ha ingresado IVA SII para este mes. "
                f"Saldo arrastrado: {opening_balance:.2f}. "
                f"Diferencia TAG + contador retenido menos pagado: {charges_total:.2f}."
            )
        if balance > 0:
            return (
                f"Saldo a favor luego de arrastrar {opening_balance:.2f}, "
                f"sumar diferencia IVA de {tax_balance:.2f}, "
                f"diferencia TAG de {tag_balance:.2f} y diferencia contador de {accountant_balance:.2f}."
            )
        if balance < 0:
            return (
                f"Saldo en contra luego de arrastrar {opening_balance:.2f}, "
                f"sumar diferencia IVA de {tax_balance:.2f}, "
                f"diferencia TAG de {tag_balance:.2f} y diferencia contador de {accountant_balance:.2f}."
            )
        return (
            f"Saldo cuadrado: arrastre {opening_balance:.2f}, "
            f"diferencia IVA de {tax_balance:.2f}, "
            f"diferencia TAG de {tag_balance:.2f} y diferencia contador de {accountant_balance:.2f}."
        )
