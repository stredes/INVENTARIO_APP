from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from database.connection import DB_PATH
from models.invoice import Invoice
from models.reconciliation import Reconciliation
from services.export_service import ExportService
from services.invoice_service import InvoiceService
from services.report_service import ReportService
from services.reconciliation_service import ReconciliationService
from services.settings_service import SettingsService
from services.update_service import UpdateService
from utils.app_metadata import APP_NAME, APP_VERSION, GITHUB_REPOSITORY
from utils.paths import get_backup_dir
from utils.formatters import format_currency, month_label
from utils.validators import (
    validate_invoice_date,
    validate_month,
    validate_positive_number,
    validate_required,
)


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class FacturionApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} | Control contable mensual")
        self.geometry("1600x980")
        self.minsize(1220, 760)
        if os.name == "nt":
            try:
                self.state("zoomed")
            except tk.TclError:
                pass

        self.current_invoice_id: int | None = None
        self.current_vat_rate = SettingsService.get_vat_rate()
        self.selected_month = tk.StringVar(value=str(datetime.today().month))
        self.selected_year = tk.StringVar(value=str(datetime.today().year))
        self.search_var = tk.StringVar()
        self.invoice_sort_state: dict[str, bool] = {}
        self.history_sort_state: dict[str, bool] = {}

        self._configure_styles()
        self._build_layout()
        self.reset_form()
        self.refresh_all()

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#18212f",
            foreground="#e5e7eb",
            fieldbackground="#18212f",
            rowheight=30,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background="#253246",
            foreground="#f9fafb",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Treeview", background=[("selected", "#0f766e")])

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=18)
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Facturion",
            font=ctk.CTkFont(size=28, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 4))

        ctk.CTkLabel(
            header,
            text=f"Control mensual de facturas, IVA acumulado y conciliación con SII | v{APP_VERSION}",
            text_color="#b6c2d2",
            font=ctk.CTkFont(size=14),
        ).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))

        header_actions = ctk.CTkFrame(header, fg_color="transparent")
        header_actions.grid(row=0, column=1, rowspan=2, sticky="e", padx=18)
        ctk.CTkButton(header_actions, text="Actualizar app", command=self.check_for_updates).pack(side="left", padx=6)
        ctk.CTkButton(header_actions, text="Respaldar BD", command=self.backup_database).pack(side="left", padx=6)
        ctk.CTkButton(header_actions, text="Configurar IVA", command=self.configure_vat_rate).pack(side="left", padx=6)

        body = ctk.CTkFrame(self, corner_radius=18)
        body.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_form_panel(body)
        self._build_main_panel(body)

    def _build_form_panel(self, parent: ctk.CTkFrame) -> None:
        panel = ctk.CTkScrollableFrame(parent, width=340, corner_radius=18)
        panel.grid(row=0, column=0, sticky="nsw", padx=(16, 10), pady=16)

        ctk.CTkLabel(
            panel,
            text="Ingreso de factura",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(18, 14))

        self.invoice_number_entry = self._labeled_entry(panel, "Número de factura")
        self.invoice_date_entry = self._labeled_entry(panel, "Fecha (YYYY-MM-DD)")
        self.client_entry = self._labeled_entry(panel, "Cliente")
        self.description_entry = self._labeled_entry(panel, "Descripción o detalle")
        self.net_amount_entry = self._labeled_entry(panel, "Monto neto")
        self.tag_amount_entry = self._labeled_entry(panel, "Cobro TAG")
        self.accountant_amount_entry = self._labeled_entry(panel, "Cobro contador")

        self.calculation_preview = ctk.CTkTextbox(panel, height=96, corner_radius=12)
        self.calculation_preview.pack(fill="x", padx=18, pady=(8, 10))

        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(4, 8))
        ctk.CTkButton(actions, text="Guardar factura", command=self.save_invoice).pack(fill="x", pady=5)
        ctk.CTkButton(actions, text="Nuevo registro", fg_color="#334155", command=self.reset_form).pack(fill="x", pady=5)
        ctk.CTkButton(
            actions,
            text="Eliminar seleccionada",
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            command=self.delete_selected_invoice,
        ).pack(fill="x", pady=5)

        help_box = ctk.CTkTextbox(panel, height=180, corner_radius=12)
        help_box.pack(fill="both", expand=True, padx=18, pady=(8, 18))
        help_box.insert(
            "1.0",
            "Validaciones incluidas:\n"
            "- Campos obligatorios\n"
            "- Fecha válida en formato YYYY-MM-DD\n"
            "- Montos positivos\n"
            "- Advertencia por factura duplicada\n\n"
            "Flujo sugerido:\n"
            "1. Registra facturas durante el mes.\n"
            "2. Revisa acumulados.\n"
            "3. Ingresa el IVA SII.\n"
            "4. Evalúa si el saldo queda a favor o en contra.",
        )
        help_box.configure(state="disabled")

    def _build_main_panel(self, parent: ctk.CTkFrame) -> None:
        panel = ctk.CTkFrame(parent, corner_radius=18)
        panel.grid(row=0, column=1, sticky="nsew", padx=(10, 16), pady=16)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        self._build_dashboard(panel)

        tabs = ctk.CTkTabview(panel, corner_radius=16)
        tabs.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        tabs.add("Facturas")
        tabs.add("Conciliación")
        tabs.add("Historial")

        facturas_tab = tabs.tab("Facturas")
        facturas_tab.grid_columnconfigure(0, weight=3)
        facturas_tab.grid_columnconfigure(1, weight=2)
        facturas_tab.grid_rowconfigure(0, weight=1)

        conciliacion_tab = tabs.tab("Conciliación")
        conciliacion_tab.grid_columnconfigure(0, weight=2)
        conciliacion_tab.grid_columnconfigure(1, weight=3)
        conciliacion_tab.grid_rowconfigure(0, weight=1)

        historial_tab = tabs.tab("Historial")
        historial_tab.grid_columnconfigure(0, weight=1)
        historial_tab.grid_rowconfigure(0, weight=1)

        self._build_invoice_table(facturas_tab)
        self._build_summary_panel(facturas_tab)
        self._build_reconciliation_panel(conciliacion_tab)
        self._build_chart_panel(conciliacion_tab)
        self._build_history_panel(historial_tab)

    def _build_dashboard(self, parent: ctk.CTkFrame) -> None:
        frame = ctk.CTkFrame(parent, corner_radius=16)
        frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        frame.grid_columnconfigure((0, 1, 2), weight=1)
        self.dashboard_cards: dict[str, ctk.CTkLabel] = {}

        cards = [
            ("Saldo arrastrado", "opening_balance"),
            ("Diferencia IVA", "tax_balance"),
            ("Diferencia TAG", "tag_balance"),
            ("Diferencia contador", "accountant_balance"),
            ("TAG retenido", "tag_amount"),
            ("Contador retenido", "accountant_amount"),
            ("Estado conciliación", "balance_status"),
            ("Saldo final", "balance"),
        ]
        for index, (label, key) in enumerate(cards):
            card = ctk.CTkFrame(frame, corner_radius=14, fg_color="#142031")
            card.grid(row=index // 3, column=index % 3, sticky="ew", padx=8, pady=8)
            ctk.CTkLabel(card, text=label, text_color="#9fb1c7").pack(anchor="w", padx=12, pady=(10, 2))
            value = ctk.CTkLabel(card, text="--", font=ctk.CTkFont(size=20, weight="bold"))
            value.pack(anchor="w", padx=12, pady=(0, 10))
            self.dashboard_cards[key] = value

    def _build_invoice_table(self, parent: ctk.CTkFrame) -> None:
        container = ctk.CTkFrame(parent, corner_radius=16)
        container.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(container, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))

        ctk.CTkLabel(
            top,
            text="Facturas registradas",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w")

        filters = ctk.CTkFrame(top, fg_color="transparent")
        filters.pack(fill="x", pady=(10, 0))
        self.search_entry = ctk.CTkEntry(filters, textvariable=self.search_var, width=220, placeholder_text="Buscar cliente, fecha o número")
        self.search_entry.pack(side="left", padx=(0, 8))
        self.month_option = ctk.CTkOptionMenu(filters, values=[str(i) for i in range(1, 13)], variable=self.selected_month, width=90)
        self.month_option.pack(side="left", padx=8)
        current_year = datetime.today().year
        year_values = [str(year) for year in range(current_year - 5, current_year + 6)]
        self.year_option = ctk.CTkOptionMenu(filters, values=year_values, variable=self.selected_year, width=100)
        self.year_option.pack(side="left", padx=8)
        ctk.CTkButton(filters, text="Filtrar", command=self.refresh_all).pack(side="left", padx=8)
        ctk.CTkButton(filters, text="Mes actual", fg_color="#334155", command=self.reset_filters_to_current_month).pack(side="left", padx=8)
        ctk.CTkButton(filters, text="Exportar Excel", command=self.export_invoices_excel).pack(side="right", padx=8)

        columns = ("id", "numero", "fecha", "cliente", "neto", "iva", "tag", "contador", "total")
        self.invoice_tree = ttk.Treeview(container, columns=columns, show="headings", height=12)
        headings = {
            "id": "ID",
            "numero": "Factura",
            "fecha": "Fecha",
            "cliente": "Cliente",
            "neto": "Neto",
            "iva": "IVA",
            "tag": "TAG",
            "contador": "Contador",
            "total": "Total",
        }
        widths = {"id": 60, "numero": 110, "fecha": 110, "cliente": 190, "neto": 110, "iva": 110, "tag": 90, "contador": 110, "total": 120}
        for column in columns:
            self.invoice_tree.heading(
                column,
                text=headings[column],
                command=lambda current=column: self.sort_treeview(
                    tree=self.invoice_tree,
                    column=current,
                    sort_state=self.invoice_sort_state,
                    heading_map=headings,
                ),
            )
            self.invoice_tree.column(column, width=widths[column], anchor="center")
        self.invoice_tree.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.invoice_tree.bind("<<TreeviewSelect>>", self.load_selected_invoice)

    def _build_summary_panel(self, parent: ctk.CTkFrame) -> None:
        container = ctk.CTkScrollableFrame(parent, corner_radius=16)
        container.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        ctk.CTkLabel(
            container,
            text="Resumen mensual",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(16, 12))
        self.summary_labels: dict[str, ctk.CTkLabel] = {}
        for label, key in [
            ("Cantidad de facturas", "count"),
            ("Total neto", "net_amount"),
            ("IVA acumulado", "vat_amount"),
            ("TAG retenido", "tag_amount"),
            ("TAG pagado real", "actual_tag_paid"),
            ("Diferencia TAG", "tag_balance"),
            ("Contador retenido", "accountant_amount"),
            ("Contador pagado real", "actual_accountant_paid"),
            ("Diferencia contador", "accountant_balance"),
            ("Total facturado", "total_amount"),
            ("IVA informado SII", "sii_vat_amount"),
            ("Saldo arrastrado", "opening_balance"),
            ("Diferencia IVA del mes", "tax_balance"),
            ("Saldo final del mes", "balance"),
            ("Estado", "balance_status"),
        ]:
            box = ctk.CTkFrame(container, fg_color="#132131", corner_radius=12)
            box.pack(fill="x", padx=16, pady=5)
            ctk.CTkLabel(box, text=label, text_color="#9fb1c7").pack(anchor="w", padx=14, pady=(10, 2))
            value = ctk.CTkLabel(box, text="--", font=ctk.CTkFont(size=18, weight="bold"))
            value.pack(anchor="w", padx=14, pady=(0, 10))
            self.summary_labels[key] = value
        self.summary_message = ctk.CTkLabel(container, text="", wraplength=360, justify="left", text_color="#cbd5e1")
        self.summary_message.pack(fill="x", padx=16, pady=(12, 12))
        ctk.CTkButton(container, text="Exportar resumen CSV", command=self.export_summary_csv).pack(fill="x", padx=16, pady=4)
        ctk.CTkButton(container, text="Imprimir reporte mensual", fg_color="#334155", command=self.print_monthly_report).pack(fill="x", padx=16, pady=(4, 16))

    def _build_reconciliation_panel(self, parent: ctk.CTkFrame) -> None:
        container = ctk.CTkScrollableFrame(parent, corner_radius=16)
        container.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ctk.CTkLabel(
            container,
            text="Conciliación IVA SII",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(16, 12))

        month_year = ctk.CTkFrame(container, fg_color="transparent")
        month_year.pack(fill="x", padx=16, pady=(0, 8))
        self.sii_month_option = ctk.CTkOptionMenu(month_year, values=[str(i) for i in range(1, 13)], variable=self.selected_month, width=120)
        self.sii_month_option.pack(side="left", padx=(0, 8))
        self.sii_year_option = ctk.CTkOptionMenu(month_year, values=self.year_option.cget("values"), variable=self.selected_year, width=120)
        self.sii_year_option.pack(side="left", padx=8)

        self.sii_vat_entry = self._labeled_entry(container, "IVA informado o declarado en SII")
        self.actual_tag_paid_entry = self._labeled_entry(container, "TAG pagado real del mes")
        self.actual_accountant_paid_entry = self._labeled_entry(container, "Contador pagado real del mes")
        self.sii_observation_entry = self._labeled_entry(container, "Observación opcional")

        ctk.CTkButton(container, text="Guardar conciliación", command=self.save_reconciliation).pack(fill="x", padx=16, pady=(8, 8))
        ctk.CTkButton(container, text="Exportar conciliación Excel", fg_color="#334155", command=self.export_reconciliation_excel).pack(fill="x", padx=16, pady=(0, 16))

    def _build_chart_panel(self, parent: ctk.CTkFrame) -> None:
        container = ctk.CTkFrame(parent, corner_radius=16)
        container.grid(row=0, column=1, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            container,
            text="Gráfico mensual",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        self.figure = Figure(figsize=(5.2, 4.2), dpi=100)
        self.axis = self.figure.add_subplot(111)
        self.figure.patch.set_facecolor("#101826")
        self.axis.set_facecolor("#101826")
        self.chart_canvas = FigureCanvasTkAgg(self.figure, master=container)
        self.chart_canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

    def _build_history_panel(self, parent: ctk.CTkFrame) -> None:
        container = ctk.CTkFrame(parent, corner_radius=16)
        container.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(container, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            top,
            text="Historial mensual",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        actions = ctk.CTkFrame(top, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(actions, text="Ver mes seleccionado", command=self.apply_selected_history_month).pack(side="left", padx=6)
        ctk.CTkButton(actions, text="Exportar historial CSV", fg_color="#334155", command=self.export_history_csv).pack(side="left", padx=6)

        columns = ("mes", "facturas", "iva", "tag_dif", "cont_dif", "sii", "arrastre", "saldo", "estado")
        table_frame = ctk.CTkFrame(container, fg_color="transparent")
        table_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        self.history_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=14)
        headings = {
            "mes": "Mes",
            "facturas": "Facturas",
            "iva": "Dif. IVA",
            "tag_dif": "Dif. TAG",
            "cont_dif": "Dif. contador",
            "sii": "IVA SII",
            "arrastre": "Saldo arrastrado",
            "saldo": "Saldo",
            "estado": "Estado",
        }
        for column in columns:
            self.history_tree.heading(
                column,
                text=headings[column],
                command=lambda current=column: self.sort_treeview(
                    tree=self.history_tree,
                    column=current,
                    sort_state=self.history_sort_state,
                    heading_map=headings,
                ),
            )
            self.history_tree.column(column, anchor="center", width=140, minwidth=100)
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        self.history_tree.bind("<Double-1>", self.apply_selected_history_month)

        history_y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.history_tree.yview)
        history_y_scroll.grid(row=0, column=1, sticky="ns")
        history_x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.history_tree.xview)
        history_x_scroll.grid(row=1, column=0, sticky="ew")
        self.history_tree.configure(yscrollcommand=history_y_scroll.set, xscrollcommand=history_x_scroll.set)

        self.history_detail_label = ctk.CTkLabel(
            container,
            text="Selecciona un mes del historial para revisar su estado, observación y cargarlo en los paneles superiores.",
            text_color="#cbd5e1",
            justify="left",
            wraplength=1400,
        )
        self.history_detail_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))

    def _labeled_entry(self, parent: ctk.CTkBaseClass, label_text: str) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label_text, text_color="#9fb1c7").pack(anchor="w", padx=18, pady=(4, 2))
        entry = ctk.CTkEntry(parent, height=36)
        entry.pack(fill="x", padx=18, pady=(0, 6))
        return entry

    def sort_treeview(
        self,
        tree: ttk.Treeview,
        column: str,
        sort_state: dict[str, bool],
        heading_map: dict[str, str],
    ) -> None:
        reverse = sort_state.get(column, False)
        rows = [(tree.set(item, column), item) for item in tree.get_children("")]
        rows.sort(key=lambda row: self._tree_sort_key(row[0]), reverse=reverse)

        for index, (_, item) in enumerate(rows):
            tree.move(item, "", index)

        for key, title in heading_map.items():
            arrow = ""
            if key == column:
                arrow = " ↓" if reverse else " ↑"
            tree.heading(
                key,
                text=f"{title}{arrow}",
                command=lambda current=key: self.sort_treeview(
                    tree=tree,
                    column=current,
                    sort_state=sort_state,
                    heading_map=heading_map,
                ),
            )

        sort_state[column] = not reverse

    def _tree_sort_key(self, value: str) -> tuple[int, object]:
        cleaned = value.strip()
        if cleaned.startswith("$"):
            normalized = (
                cleaned.replace("$", "")
                .replace(" ", "")
                .replace(".", "")
                .replace(",", ".")
            )
            try:
                return (0, float(normalized))
            except ValueError:
                pass

        try:
            parsed_date = datetime.strptime(cleaned, "%Y-%m-%d")
            return (1, parsed_date)
        except ValueError:
            pass

        if "/" in cleaned and len(cleaned) == 7:
            try:
                month, year = cleaned.split("/")
                return (1, datetime(int(year), int(month), 1))
            except ValueError:
                pass

        try:
            return (0, float(cleaned))
        except ValueError:
            return (2, cleaned.lower())

    def refresh_all(self) -> None:
        self.refresh_invoice_table()
        self.refresh_summary()
        self.refresh_dashboard()
        self.refresh_history()
        self.refresh_chart()
        self.load_reconciliation_fields()

    def refresh_invoice_table(self) -> None:
        for item in self.invoice_tree.get_children():
            self.invoice_tree.delete(item)

        invoices = InvoiceService.list_all(
            search=self.search_var.get(),
            month=self.selected_month.get(),
            year=self.selected_year.get(),
        )
        for invoice in invoices:
            self.invoice_tree.insert(
                "",
                "end",
                values=(
                    invoice["id"],
                    invoice["invoice_number"],
                    invoice["invoice_date"],
                    invoice["client"],
                    format_currency(invoice["net_amount"]),
                    format_currency(invoice["vat_amount"]),
                    format_currency(invoice["tag_amount"]),
                    format_currency(invoice["accountant_amount"]),
                    format_currency(invoice["total_amount"]),
                ),
            )

    def refresh_summary(self) -> None:
        summary = ReportService.monthly_summary(self.selected_month.get(), self.selected_year.get())
        self.summary_labels["count"].configure(text=str(summary["count"]))
        for key in (
            "net_amount",
            "vat_amount",
            "tag_amount",
            "actual_tag_paid",
            "tag_balance",
            "accountant_amount",
            "actual_accountant_paid",
            "accountant_balance",
            "total_amount",
            "sii_vat_amount",
            "opening_balance",
            "tax_balance",
            "balance",
        ):
            self.summary_labels[key].configure(text=format_currency(summary[key]))
        self.summary_labels["balance_status"].configure(text=summary["balance_status"])
        self.summary_message.configure(text=summary["balance_message"])

    def refresh_dashboard(self) -> None:
        summary = ReportService.current_month_summary()
        self.dashboard_cards["opening_balance"].configure(text=format_currency(summary["opening_balance"]))
        self.dashboard_cards["tax_balance"].configure(text=format_currency(summary["tax_balance"]))
        self.dashboard_cards["tag_balance"].configure(text=format_currency(summary["tag_balance"]))
        self.dashboard_cards["accountant_balance"].configure(text=format_currency(summary["accountant_balance"]))
        self.dashboard_cards["tag_amount"].configure(text=format_currency(summary["tag_amount"]))
        self.dashboard_cards["accountant_amount"].configure(text=format_currency(summary["accountant_amount"]))
        self.dashboard_cards["balance_status"].configure(text=summary["balance_status"])
        self.dashboard_cards["balance"].configure(text=format_currency(summary["balance"]))

    def refresh_history(self) -> None:
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        for row in ReportService.grouped_history():
            self.history_tree.insert(
                "",
                "end",
                values=(
                    month_label(row["month"]),
                    row["count"],
                    format_currency(row["tax_balance"]),
                    format_currency(row["tag_balance"]),
                    format_currency(row["accountant_balance"]),
                    format_currency(row["sii_vat_amount"]),
                    format_currency(row["opening_balance"]),
                    format_currency(row["balance"]),
                    row["balance_status"],
                ),
                tags=(row["month"], row["observation"]),
            )

    def refresh_chart(self) -> None:
        history = ReportService.grouped_history()[:6]
        self.axis.clear()
        self.axis.set_facecolor("#101826")
        self.axis.tick_params(axis="x", colors="#cbd5e1", rotation=20)
        self.axis.tick_params(axis="y", colors="#cbd5e1")
        if history:
            labels = [month_label(item["month"]) for item in reversed(history)]
            vat_values = [item["vat_amount"] for item in reversed(history)]
            sii_values = [item["sii_vat_amount"] for item in reversed(history)]
            self.axis.plot(labels, vat_values, marker="o", color="#22c55e", label="IVA interno")
            self.axis.plot(labels, sii_values, marker="o", color="#38bdf8", label="IVA SII")
            self.axis.legend(facecolor="#101826", edgecolor="#334155", labelcolor="#e2e8f0")
        self.axis.set_title("Comparación IVA interno vs SII", color="#f8fafc")
        self.figure.tight_layout()
        self.chart_canvas.draw()

    def collect_invoice_form(self) -> Invoice:
        invoice_number = validate_required(self.invoice_number_entry.get(), "Número de factura")
        invoice_date = validate_invoice_date(self.invoice_date_entry.get())
        client = validate_required(self.client_entry.get(), "Cliente")
        description = self.description_entry.get().strip()
        net_amount = validate_positive_number(self.net_amount_entry.get(), "Monto neto", allow_zero=False)
        tag_amount = validate_positive_number(self.tag_amount_entry.get() or "0", "Cobro TAG")
        accountant_amount = validate_positive_number(self.accountant_amount_entry.get() or "0", "Cobro contador")

        totals = ReportService.calculate_invoice_totals(
            net_amount=net_amount,
            vat_rate=self.current_vat_rate,
            tag_amount=tag_amount,
            accountant_amount=accountant_amount,
        )

        self.calculation_preview.configure(state="normal")
        self.calculation_preview.delete("1.0", "end")
        self.calculation_preview.insert(
            "1.0",
            f"Tasa IVA actual: {self.current_vat_rate:.2f}%\n"
            f"IVA calculado: {format_currency(totals['vat_amount'])}\n"
            f"Total final: {format_currency(totals['total_amount'])}",
        )
        self.calculation_preview.configure(state="disabled")

        return Invoice(
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            client=client,
            description=description,
            net_amount=net_amount,
            vat_rate=self.current_vat_rate,
            vat_amount=totals["vat_amount"],
            tag_amount=tag_amount,
            accountant_amount=accountant_amount,
            total_amount=totals["total_amount"],
        )

    def save_invoice(self) -> None:
        try:
            invoice = self.collect_invoice_form()
            duplicate = InvoiceService.exists_duplicate(
                invoice.invoice_number,
                invoice.invoice_date,
                exclude_id=self.current_invoice_id,
            )
            if duplicate:
                proceed = messagebox.askyesno(
                    "Factura duplicada",
                    "Ya existe una factura con el mismo número y fecha. ¿Deseas continuar?",
                )
                if not proceed:
                    return

            if self.current_invoice_id is None:
                InvoiceService.create(invoice)
                messagebox.showinfo("Factura guardada", "La factura fue registrada correctamente.")
            else:
                InvoiceService.update(self.current_invoice_id, invoice)
                messagebox.showinfo("Factura actualizada", "La factura fue actualizada correctamente.")
            self.reset_form()
            self.refresh_all()
        except ValueError as error:
            messagebox.showerror("Validación", str(error))
        except Exception as error:
            messagebox.showerror("Error", f"No se pudo guardar la factura.\n{error}")

    def reset_form(self) -> None:
        self.current_invoice_id = None
        for entry in (
            self.invoice_number_entry,
            self.invoice_date_entry,
            self.client_entry,
            self.description_entry,
            self.net_amount_entry,
            self.tag_amount_entry,
            self.accountant_amount_entry,
        ):
            entry.delete(0, "end")
        self.invoice_date_entry.insert(0, datetime.today().strftime("%Y-%m-%d"))
        self.tag_amount_entry.insert(0, "0")
        self.accountant_amount_entry.insert(0, "0")
        self.calculation_preview.configure(state="normal")
        self.calculation_preview.delete("1.0", "end")
        self.calculation_preview.insert(
            "1.0",
            "IVA calculado automáticamente según la tasa configurada.\n"
            "Total = neto + IVA + TAG + contador.",
        )
        self.calculation_preview.configure(state="disabled")

    def load_selected_invoice(self, _event: object | None = None) -> None:
        selected = self.invoice_tree.selection()
        if not selected:
            return
        invoice_id = int(self.invoice_tree.item(selected[0], "values")[0])
        invoice = InvoiceService.get(invoice_id)
        if not invoice:
            return

        self.current_invoice_id = invoice_id
        self.invoice_number_entry.delete(0, "end")
        self.invoice_number_entry.insert(0, invoice["invoice_number"])
        self.invoice_date_entry.delete(0, "end")
        self.invoice_date_entry.insert(0, invoice["invoice_date"])
        self.client_entry.delete(0, "end")
        self.client_entry.insert(0, invoice["client"])
        self.description_entry.delete(0, "end")
        self.description_entry.insert(0, invoice["description"])
        self.net_amount_entry.delete(0, "end")
        self.net_amount_entry.insert(0, str(invoice["net_amount"]))
        self.tag_amount_entry.delete(0, "end")
        self.tag_amount_entry.insert(0, str(invoice["tag_amount"]))
        self.accountant_amount_entry.delete(0, "end")
        self.accountant_amount_entry.insert(0, str(invoice["accountant_amount"]))

    def delete_selected_invoice(self) -> None:
        selected = self.invoice_tree.selection()
        if not selected:
            messagebox.showwarning("Selección requerida", "Selecciona una factura para eliminar.")
            return
        invoice_id = int(self.invoice_tree.item(selected[0], "values")[0])
        confirmed = messagebox.askyesno("Eliminar factura", "¿Seguro que deseas eliminar la factura seleccionada?")
        if not confirmed:
            return
        InvoiceService.delete(invoice_id)
        self.reset_form()
        self.refresh_all()

    def reset_filters_to_current_month(self) -> None:
        self.search_var.set("")
        self.selected_month.set(str(datetime.today().month))
        self.selected_year.set(str(datetime.today().year))
        self.refresh_all()

    def apply_selected_history_month(self, _event: object | None = None) -> None:
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showwarning("Selección requerida", "Selecciona un mes del historial.")
            return

        item = self.history_tree.item(selected[0])
        tags = item.get("tags", [])
        if not tags:
            return

        month_key = tags[0]
        observation = tags[1] if len(tags) > 1 else ""
        year_value, month_value = month_key.split("-")
        self.selected_year.set(year_value)
        self.selected_month.set(str(int(month_value)))
        self.refresh_all()

        summary = ReportService.monthly_summary(str(int(month_value)), year_value)
        observation_text = observation if observation else "Sin observación registrada."
        self.history_detail_label.configure(
            text=(
                f"Mes seleccionado: {month_label(month_key)} | "
                f"Saldo arrastrado: {format_currency(summary['opening_balance'])} | "
                f"Diferencia IVA: {format_currency(summary['tax_balance'])} | "
                f"Diferencia TAG: {format_currency(summary['tag_balance'])} | "
                f"Diferencia contador: {format_currency(summary['accountant_balance'])} | "
                f"Estado: {summary['balance_status']} | "
                f"Saldo: {format_currency(summary['balance'])} | "
                f"Observación SII: {observation_text}"
            )
        )

    def load_reconciliation_fields(self) -> None:
        month_value = self.selected_month.get() or str(datetime.today().month)
        year_value = self.selected_year.get() or str(datetime.today().year)
        month_key = f"{year_value}-{int(month_value):02d}"
        row = ReconciliationService.get_by_month(month_key)
        self.sii_vat_entry.delete(0, "end")
        self.actual_tag_paid_entry.delete(0, "end")
        self.actual_accountant_paid_entry.delete(0, "end")
        self.sii_observation_entry.delete(0, "end")
        if row:
            self.sii_vat_entry.insert(0, str(row["sii_vat_amount"]))
            self.actual_tag_paid_entry.insert(0, str(row.get("actual_tag_paid", 0)))
            self.actual_accountant_paid_entry.insert(0, str(row.get("actual_accountant_paid", 0)))
            self.sii_observation_entry.insert(0, row["observation"] or "")
        else:
            self.actual_tag_paid_entry.insert(0, "0")
            self.actual_accountant_paid_entry.insert(0, "0")

    def save_reconciliation(self) -> None:
        try:
            month_key = validate_month(self.selected_month.get(), self.selected_year.get())
            sii_vat_amount = validate_positive_number(self.sii_vat_entry.get(), "IVA informado por SII")
            actual_tag_paid = validate_positive_number(self.actual_tag_paid_entry.get() or "0", "TAG pagado real")
            actual_accountant_paid = validate_positive_number(
                self.actual_accountant_paid_entry.get() or "0",
                "Contador pagado real",
            )
            observation = self.sii_observation_entry.get().strip()
            ReconciliationService.upsert(
                Reconciliation(
                    month=month_key,
                    sii_vat_amount=sii_vat_amount,
                    actual_tag_paid=actual_tag_paid,
                    actual_accountant_paid=actual_accountant_paid,
                    observation=observation,
                )
            )
            self.refresh_all()
            messagebox.showinfo("Conciliación guardada", "La conciliación con SII fue guardada correctamente.")
        except ValueError as error:
            messagebox.showerror("Validación", str(error))
        except Exception as error:
            messagebox.showerror("Error", f"No se pudo guardar la conciliación.\n{error}")

    def configure_vat_rate(self) -> None:
        dialog = ctk.CTkInputDialog(text="Ingresa el nuevo porcentaje de IVA:", title="Configurar IVA")
        value = dialog.get_input()
        if value is None:
            return
        try:
            vat_rate = validate_positive_number(value, "IVA", allow_zero=False)
            SettingsService.update_vat_rate(vat_rate)
            self.current_vat_rate = vat_rate
            self.reset_form()
            messagebox.showinfo("IVA actualizado", "La tasa de IVA fue actualizada correctamente.")
        except ValueError as error:
            messagebox.showerror("Validación", str(error))

    def check_for_updates(self) -> None:
        try:
            release = UpdateService.get_latest_release()
        except Exception as error:
            messagebox.showerror("Actualización", str(error))
            return

        if not UpdateService.is_newer_version(release.version, APP_VERSION):
            messagebox.showinfo(
                "Actualización",
                f"Ya estás usando la versión más reciente: v{APP_VERSION}.",
            )
            return

        notes = (release.body or "").strip()
        notes_preview = notes[:300] + ("..." if len(notes) > 300 else "")
        prompt = (
            f"Versión actual: v{APP_VERSION}\n"
            f"Nueva versión disponible: v{release.version}\n"
            f"Repositorio: {GITHUB_REPOSITORY or 'No configurado'}\n\n"
            f"Notas del release:\n{notes_preview or 'Sin notas publicadas.'}\n\n"
        )

        if not UpdateService.is_frozen():
            messagebox.showinfo(
                "Actualización disponible",
                prompt
                + "La actualización automática solo funciona desde la app instalada con el ejecutable. "
                + "Desde esta ejecución de desarrollo debes descargar e instalar el Setup.exe del release.",
            )
            return

        proceed = messagebox.askyesno(
            "Actualizar aplicación",
            prompt + "¿Deseas descargar e instalar esta versión ahora?",
        )
        if not proceed:
            return

        try:
            installer_path = UpdateService.download_installer(release)
            UpdateService.launch_updater(installer_path, os.getpid())
        except Exception as error:
            messagebox.showerror("Actualización", f"No se pudo iniciar la actualización.\n{error}")
            return

        messagebox.showinfo(
            "Actualización iniciada",
            "Se descargó la nueva versión. La aplicación se cerrará para instalar la actualización.",
        )
        self.after(250, self.destroy)

    def backup_database(self) -> None:
        backup_dir = get_backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = backup_dir / f"facturion_backup_{timestamp}.db"
        shutil.copy2(DB_PATH, destination)
        messagebox.showinfo("Respaldo listo", f"Se creó un respaldo en:\n{destination}")

    def export_invoices_excel(self) -> None:
        invoices = InvoiceService.list_all(
            search=self.search_var.get(),
            month=self.selected_month.get(),
            year=self.selected_year.get(),
        )
        if not invoices:
            messagebox.showwarning("Sin datos", "No hay facturas para exportar.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        headers = ["ID", "Factura", "Fecha", "Cliente", "Descripción", "Neto", "IVA", "TAG", "Contador", "Total"]
        rows = [
            (
                item["id"],
                item["invoice_number"],
                item["invoice_date"],
                item["client"],
                item["description"],
                item["net_amount"],
                item["vat_amount"],
                item["tag_amount"],
                item["accountant_amount"],
                item["total_amount"],
            )
            for item in invoices
        ]
        ExportService.export_to_excel(path, "Facturas", headers, rows)
        messagebox.showinfo("Exportación lista", "El listado de facturas fue exportado correctamente.")

    def export_summary_csv(self) -> None:
        summary = ReportService.monthly_summary(self.selected_month.get(), self.selected_year.get())
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        headers = [
            "Mes",
            "Facturas",
            "Neto",
            "IVA",
            "TAG retenido",
            "TAG pagado real",
            "Diferencia TAG",
            "Contador retenido",
            "Contador pagado real",
            "Diferencia contador",
            "Total",
            "IVA SII",
            "Saldo arrastrado",
            "Diferencia IVA",
            "Saldo final",
            "Estado",
        ]
        rows = [[
            f"{int(self.selected_month.get()):02d}/{self.selected_year.get()}",
            summary["count"],
            summary["net_amount"],
            summary["vat_amount"],
            summary["tag_amount"],
            summary["actual_tag_paid"],
            summary["tag_balance"],
            summary["accountant_amount"],
            summary["actual_accountant_paid"],
            summary["accountant_balance"],
            summary["total_amount"],
            summary["sii_vat_amount"],
            summary["opening_balance"],
            summary["tax_balance"],
            summary["balance"],
            summary["balance_status"],
        ]]
        ExportService.export_to_csv(path, headers, rows)
        messagebox.showinfo("Exportación lista", "El resumen mensual fue exportado correctamente.")

    def export_reconciliation_excel(self) -> None:
        rows_data = ReconciliationService.list_all()
        if not rows_data:
            messagebox.showwarning("Sin datos", "No hay conciliaciones registradas para exportar.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        headers = ["Mes", "IVA SII", "TAG pagado real", "Contador pagado real", "Observación"]
        rows = [
            (
                item["month"],
                item["sii_vat_amount"],
                item.get("actual_tag_paid", 0),
                item.get("actual_accountant_paid", 0),
                item["observation"],
            )
            for item in rows_data
        ]
        ExportService.export_to_excel(path, "Conciliacion_SII", headers, rows)
        messagebox.showinfo("Exportación lista", "La conciliación mensual fue exportada correctamente.")

    def export_history_csv(self) -> None:
        history = ReportService.grouped_history()
        if not history:
            messagebox.showwarning("Sin datos", "No hay historial mensual para exportar.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        headers = [
            "Mes",
            "Facturas",
            "Neto",
            "IVA interno",
            "TAG retenido",
            "TAG pagado real",
            "Diferencia TAG",
            "Contador retenido",
            "Contador pagado real",
            "Diferencia contador",
            "Total facturado",
            "IVA SII",
            "Saldo arrastrado",
            "Diferencia IVA",
            "Saldo final",
            "Estado",
            "Observación",
        ]
        rows = [
            (
                row["month"],
                row["count"],
                row["net_amount"],
                row["vat_amount"],
                row["tag_amount"],
                row["actual_tag_paid"],
                row["tag_balance"],
                row["accountant_amount"],
                row["actual_accountant_paid"],
                row["accountant_balance"],
                row["total_amount"],
                row["sii_vat_amount"],
                row["opening_balance"],
                row["tax_balance"],
                row["balance"],
                row["balance_status"],
                row["observation"],
            )
            for row in history
        ]
        ExportService.export_to_csv(path, headers, rows)
        messagebox.showinfo("Exportación lista", "El historial mensual fue exportado correctamente.")

    def print_monthly_report(self) -> None:
        summary = ReportService.monthly_summary(self.selected_month.get(), self.selected_year.get())
        message = (
            f"Mes: {int(self.selected_month.get()):02d}/{self.selected_year.get()}\n"
            f"Facturas: {summary['count']}\n"
            f"Saldo arrastrado: {format_currency(summary['opening_balance'])}\n"
            f"IVA interno: {format_currency(summary['vat_amount'])}\n"
            f"IVA SII: {format_currency(summary['sii_vat_amount'])}\n"
            f"Diferencia IVA: {format_currency(summary['tax_balance'])}\n"
            f"TAG retenido: {format_currency(summary['tag_amount'])}\n"
            f"TAG pagado real: {format_currency(summary['actual_tag_paid'])}\n"
            f"Diferencia TAG: {format_currency(summary['tag_balance'])}\n"
            f"Contador retenido: {format_currency(summary['accountant_amount'])}\n"
            f"Contador pagado real: {format_currency(summary['actual_accountant_paid'])}\n"
            f"Diferencia contador: {format_currency(summary['accountant_balance'])}\n"
            f"Saldo final: {format_currency(summary['balance'])}\n"
            f"Estado: {summary['balance_status']}\n\n"
            "Puedes imprimir este resumen usando la función del sistema o exportarlo a CSV/Excel."
        )
        messagebox.showinfo("Reporte mensual", message)
