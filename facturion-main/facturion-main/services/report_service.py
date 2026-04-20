from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from services.invoice_service import InvoiceService
from services.reconciliation_service import ReconciliationService


class ReportService:
    @staticmethod
    def round_money(value: float) -> float:
        return float(round(value or 0))

    @staticmethod
    def calculate_invoice_totals(
        net_amount: float,
        vat_rate: float,
        tag_amount: float,
        accountant_amount: float,
        savings_amount: float = 0.0,
    ) -> dict[str, float]:
        net_amount = ReportService.round_money(net_amount)
        tag_amount = ReportService.round_money(tag_amount)
        accountant_amount = ReportService.round_money(accountant_amount)
        savings_amount = ReportService.round_money(savings_amount)
        vat_amount = ReportService.round_money(net_amount * (vat_rate / 100))
        billed_total = ReportService.round_money(net_amount + vat_amount)
        withheld_total = ReportService.round_money(tag_amount + accountant_amount + savings_amount)
        total_amount = ReportService.round_money(billed_total - withheld_total)
        return {
            "vat_amount": vat_amount,
            "billed_total": billed_total,
            "withheld_total": withheld_total,
            "total_amount": total_amount,
        }

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
    def global_summary() -> dict[str, Any]:
        history = ReportService._build_monthly_balances().values()
        totals = {
            "count": 0,
            "net_amount": 0.0,
            "vat_amount": 0.0,
            "sii_vat_amount": 0.0,
            "pending_vat_amount": 0.0,
            "tag_amount": 0.0,
            "actual_tag_paid": 0.0,
            "pending_tag_amount": 0.0,
            "accountant_amount": 0.0,
            "actual_accountant_paid": 0.0,
            "pending_accountant_amount": 0.0,
            "billed_total_amount": 0.0,
            "total_amount": 0.0,
            "company_commitments": 0.0,
            "available_savings": 0.0,
        }
        for row in history:
            totals["count"] += int(row.get("count", 0) or 0)
            for key in (
                "net_amount",
                "vat_amount",
                "sii_vat_amount",
                "tag_amount",
                "actual_tag_paid",
                "accountant_amount",
                "actual_accountant_paid",
                "billed_total_amount",
                "total_amount",
            ):
                totals[key] = ReportService.round_money(totals[key] + float(row.get(key, 0) or 0))

        totals["pending_vat_amount"] = ReportService.round_money(totals["vat_amount"] - totals["sii_vat_amount"])
        totals["pending_tag_amount"] = ReportService.round_money(totals["tag_amount"] - totals["actual_tag_paid"])
        totals["pending_accountant_amount"] = ReportService.round_money(
            totals["accountant_amount"] - totals["actual_accountant_paid"]
        )
        totals["company_commitments"] = ReportService.round_money(
            totals["pending_vat_amount"] + totals["pending_tag_amount"] + totals["pending_accountant_amount"]
        )
        totals["available_savings"] = ReportService.round_money(
            totals["total_amount"] - totals["pending_vat_amount"]
        )
        return totals

    @staticmethod
    def excel_cards_summary() -> dict[str, float]:
        invoices = InvoiceService.list_all()
        totals = ReportService.global_summary()

        received_billed_total = ReportService.round_money(
            sum(float(invoice.get("total_amount", 0) or 0) for invoice in invoices)
        )
        received_vat = ReportService.round_money(sum(float(invoice.get("vat_amount", 0) or 0) for invoice in invoices))
        received_tag = ReportService.round_money(sum(float(invoice.get("tag_amount", 0) or 0) for invoice in invoices))
        received_accountant = ReportService.round_money(
            sum(float(invoice.get("accountant_amount", 0) or 0) for invoice in invoices)
        )
        savings_received = ReportService.round_money(
            sum(float(invoice.get("savings_amount", 0) or 0) for invoice in invoices)
        )
        deposit_manuel = ReportService.round_money(
            sum(float(invoice.get("deposit_manuel_amount", 0) or 0) for invoice in invoices)
        )
        if deposit_manuel == 0:
            deposit_manuel = ReportService.round_money(
                totals["net_amount"] - totals["tag_amount"] - totals["accountant_amount"]
            )

        paid_vat = ReportService.round_money(
            sum(float(invoice.get("paid_vat_amount", 0) or 0) for invoice in invoices)
        )
        paid_accountant_base = ReportService.round_money(
            sum(float(invoice.get("paid_accountant_amount", 0) or 0) for invoice in invoices)
        )
        paid_tag = ReportService.round_money(
            sum(float(invoice.get("paid_tag_amount", 0) or 0) for invoice in invoices)
        )
        savings_paid = ReportService.round_money(
            sum(float(invoice.get("paid_savings_amount", 0) or 0) for invoice in invoices)
        )
        if paid_vat == 0 and paid_accountant_base == 0 and paid_tag == 0 and savings_paid == 0:
            paid_vat = totals["sii_vat_amount"]
            paid_accountant_base = totals["actual_accountant_paid"]
            paid_tag = totals["actual_tag_paid"]

        # The workbook's "Pago contador" card sums the detail payment and its total row.
        paid_accountant_display = ReportService.round_money(paid_accountant_base * 2)
        savings_balance = 0.0
        vat_balance = ReportService.round_money(received_vat - paid_vat)
        tag_balance = 0.0
        accountant_balance = ReportService.round_money(received_accountant - paid_accountant_base)
        total_balance = ReportService.round_money(
            vat_balance + accountant_balance
        )
        return {
            "received_billed_total": received_billed_total,
            "received_vat": received_vat,
            "received_tag": received_tag,
            "received_accountant": received_accountant,
            "received_savings": savings_received,
            "deposit_manuel": deposit_manuel,
            "paid_vat": paid_vat,
            "paid_accountant": paid_accountant_display,
            "paid_tag": paid_tag,
            "paid_savings": savings_paid,
            "vat_balance": vat_balance,
            "accountant_balance": accountant_balance,
            "tag_balance": tag_balance,
            "savings_balance": savings_balance,
            "total_balance": total_balance,
        }

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
                "billed_total_amount": 0.0,
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
            entry["billed_total_amount"] += ReportService.round_money(invoice["net_amount"] + invoice["vat_amount"])
            entry["total_amount"] += ReportService.round_money(
                invoice["net_amount"] + invoice["vat_amount"] - invoice["tag_amount"] - invoice["accountant_amount"],
            )

        all_months = set(grouped.keys()) | set(reconciliations.keys())
        if include_month:
            all_months.add(include_month)

        balanced: dict[str, dict[str, Any]] = {}
        previous_closing_balance = 0.0
        previous_tag_balance = 0.0
        previous_accountant_balance = 0.0
        accumulated_tag_retained = 0.0
        accumulated_actual_tag_paid = 0.0
        accumulated_accountant_retained = 0.0
        accumulated_actual_accountant_paid = 0.0

        for month_key in sorted(all_months):
            entry = grouped.get(month_key, {}).copy() or {
                "month": month_key,
                "count": 0,
                "net_amount": 0.0,
                "vat_amount": 0.0,
                "tag_amount": 0.0,
                "accountant_amount": 0.0,
                "billed_total_amount": 0.0,
                "total_amount": 0.0,
            }
            for key in ("net_amount", "vat_amount", "tag_amount", "accountant_amount", "billed_total_amount", "total_amount"):
                entry[key] = ReportService.round_money(entry[key])

            reconciliation = reconciliations.get(month_key)
            sii_vat = reconciliation["sii_vat_amount"] if reconciliation else 0.0
            actual_tag_paid = reconciliation["actual_tag_paid"] if reconciliation else 0.0
            actual_accountant_paid = reconciliation["actual_accountant_paid"] if reconciliation else 0.0
            tax_balance = ReportService.round_money(entry["vat_amount"] - sii_vat)
            month_tag_delta = ReportService.round_money(entry["tag_amount"] - actual_tag_paid)
            month_accountant_delta = ReportService.round_money(entry["accountant_amount"] - actual_accountant_paid)
            tag_balance = ReportService.round_money(previous_tag_balance + month_tag_delta)
            accountant_balance = ReportService.round_money(previous_accountant_balance + month_accountant_delta)
            charges_delta = ReportService.round_money(month_tag_delta + month_accountant_delta)
            charges_total = ReportService.round_money(tag_balance + accountant_balance)
            opening_balance = ReportService.round_money(previous_closing_balance)
            closing_balance = ReportService.round_money(opening_balance + tax_balance - charges_delta)

            accumulated_tag_retained = ReportService.round_money(accumulated_tag_retained + entry["tag_amount"])
            accumulated_actual_tag_paid = ReportService.round_money(accumulated_actual_tag_paid + actual_tag_paid)
            accumulated_accountant_retained = ReportService.round_money(
                accumulated_accountant_retained + entry["accountant_amount"]
            )
            accumulated_actual_accountant_paid = ReportService.round_money(accumulated_actual_accountant_paid + actual_accountant_paid)

            entry["sii_vat_amount"] = sii_vat
            entry["actual_tag_paid"] = ReportService.round_money(actual_tag_paid)
            entry["actual_accountant_paid"] = ReportService.round_money(actual_accountant_paid)
            entry["accumulated_tag_retained"] = accumulated_tag_retained
            entry["accumulated_tag_amount"] = ReportService.round_money(accumulated_tag_retained - accumulated_actual_tag_paid)
            entry["accumulated_actual_tag_paid"] = accumulated_actual_tag_paid
            entry["accumulated_accountant_retained"] = accumulated_accountant_retained
            entry["accumulated_accountant_amount"] = ReportService.round_money(
                accumulated_accountant_retained - accumulated_actual_accountant_paid
            )
            entry["accumulated_actual_accountant_paid"] = accumulated_actual_accountant_paid
            entry["month_tag_balance"] = month_tag_delta
            entry["month_accountant_balance"] = month_accountant_delta
            entry["tax_balance"] = tax_balance
            entry["tag_balance"] = tag_balance
            entry["accountant_balance"] = accountant_balance
            entry["charges_delta"] = charges_delta
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
            previous_tag_balance = tag_balance
            previous_accountant_balance = accountant_balance

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
        charges_total = ReportService.round_money(tag_balance + accountant_balance)
        if not has_reconciliation:
            return (
                "Aun no se ha ingresado IVA SII para este mes. "
                f"Saldo heredado del mes anterior: {opening_balance:.0f}. "
                f"Retenciones pendientes de TAG + contador: {charges_total:.0f}."
            )
        if balance > 0:
            return (
                f"Saldo a favor luego de heredar {opening_balance:.0f} del mes anterior, "
                f"sumar diferencia IVA de {tax_balance:.0f} y "
                f"restar saldo TAG acumulado de {tag_balance:.0f} mas saldo contador acumulado de {accountant_balance:.0f}."
            )
        if balance < 0:
            return (
                f"Saldo en contra luego de heredar {opening_balance:.0f} del mes anterior, "
                f"sumar diferencia IVA de {tax_balance:.0f} y "
                f"restar saldo TAG acumulado de {tag_balance:.0f} mas saldo contador acumulado de {accountant_balance:.0f}."
            )
        return (
            f"Saldo cuadrado: herencia del mes anterior {opening_balance:.0f}, "
            f"diferencia IVA de {tax_balance:.0f}, "
            f"restando saldo TAG acumulado de {tag_balance:.0f} y saldo contador acumulado de {accountant_balance:.0f}."
        )
