# src/gui/widgets/column_filter.py
from __future__ import annotations
import re
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk


# ------------------------------- Tipos ------------------------------------ #

FieldType = str  # "text" | "number" | "date"

TEXT_OPS = [
    "contiene",
    "no contiene",
    "=",
    "≠",
    "empieza con",
    "termina con",
    "vacío",
    "no vacío",
]

NUMBER_OPS = [
    "=",
    "≠",
    ">",
    "≥",
    "<",
    "≤",
    "entre",
    "vacío",
    "no vacío",
]

DATE_OPS = [
    "=",
    "≠",
    ">",
    "≥",
    "<",
    "≤",
    "entre",
    "hoy",
    "esta semana",
    "este mes",
    "vacío",
    "no vacío",
]


@dataclass(frozen=True)
class FilterDescriptor:
    """Descripción serializable del filtro actual."""
    field_name: str
    field_type: FieldType
    op: str
    value1: Optional[str] = None
    value2: Optional[str] = None
    case_sensitive: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "field_type": self.field_type,
            "op": self.op,
            "value1": self.value1,
            "value2": self.value2,
            "case_sensitive": self.case_sensitive,
        }


# --------------------------- Utilidades parsing --------------------------- #

_DATE_FORMATS = (
    "%d-%m-%Y", "%d/%m/%Y",
    "%Y-%m-%d", "%Y/%m/%d",
    "%d-%m-%y", "%d/%m/%y",
)


def parse_date(s: str) -> date:
    """Parsea una fecha común (dd-mm-aaaa, dd/mm/aaaa, aaaa-mm-dd, etc.)."""
    s = (s or "").strip()
    if not s:
        raise ValueError("Fecha vacía")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Formato de fecha inválido: {s}")


def parse_number(s: str) -> float:
    """
    Convierte string a número float. Acepta coma o punto decimal.
    """
    if s is None:
        raise ValueError("Número vacío")
    s_norm = s.strip().replace(",", ".")
    return float(s_norm)


def week_bounds(d: date) -> Tuple[date, date]:
    """Retorna lunes-domingo de la semana de d (ISO)."""
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def month_bounds(d: date) -> Tuple[date, date]:
    """Primer y último día del mes de d."""
    start = d.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1, day=1)
    else:
        next_month = start.replace(month=start.month + 1, day=1)
    end = next_month - timedelta(days=1)
    return start, end


# ------------------------------ Widget UI --------------------------------- #

class ColumnFilter(ttk.Frame):
    """
    Filtro de columna para Treeview u otras vistas.

    - field_name: nombre lógico/DB de la columna (para SQL y logs).
    - field_type: "text" | "number" | "date".
    - choices: lista opcional; si se provee, usa Combobox para value1.
    - on_apply: callback que recibe FilterDescriptor cuando el usuario aplica.
    - on_clear: callback opcional al limpiar.

    Métodos clave:
        get_descriptor() -> FilterDescriptor | None
        make_predicate(extractor) -> Callable[[Any], bool]
        build_sql(column_name, driver="sqlite") -> (sql, params)

    Ejemplo de uso:
        filt = ColumnFilter(parent, field_name="Producto", field_type="text",
                            on_apply=lambda d: recargar(d))
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        field_name: str,
        field_type: FieldType = "text",
        on_apply: Optional[Callable[[FilterDescriptor], None]] = None,
        on_clear: Optional[Callable[[], None]] = None,
        choices: Optional[List[str]] = None,
        case_sensitive_default: bool = False,
    ):
        super().__init__(master, padding=8)
        self.field_name = field_name
        self.field_type = field_type
        self.on_apply = on_apply
        self.on_clear = on_clear
        self.choices = choices

        # Vars
        self._op = tk.StringVar()
        self._v1 = tk.StringVar()
        self._v2 = tk.StringVar()
        self._case = tk.BooleanVar(value=case_sensitive_default)
        self._err = tk.StringVar(value="")

        # Layout
        self.columnconfigure(3, weight=1)

        # Etiqueta columna
        ttk.Label(self, text=self.field_name).grid(row=0, column=0, padx=(0, 6), sticky="w")

        # Operadores
        ops = TEXT_OPS if field_type == "text" else NUMBER_OPS if field_type == "number" else DATE_OPS
        self._op_cb = ttk.Combobox(self, values=ops, textvariable=self._op, width=14, state="readonly")
        self._op_cb.grid(row=0, column=1, padx=4, sticky="w")
        self._op_cb.bind("<<ComboboxSelected>>", self._on_op_change)

        # Value 1 (Entry o Combobox según choices)
        if choices:
            self._v1_widget = ttk.Combobox(self, values=choices, textvariable=self._v1, width=24)
        else:
            self._v1_widget = ttk.Entry(self, textvariable=self._v1, width=24)
        self._v1_widget.grid(row=0, column=2, padx=4, sticky="we")

        # Value 2 (para 'entre')
        self._v2_widget = ttk.Entry(self, textvariable=self._v2, width=18)
        self._v2_widget.grid(row=0, column=3, padx=4, sticky="we")
        self._v2_widget.grid_remove()  # oculto por defecto

        # Case sensitive solo para texto
        self._case_chk = ttk.Checkbutton(self, text="Aa", variable=self._case)
        if field_type == "text":
            self._case_chk.grid(row=0, column=4, padx=4)
        else:
            # evita ocupar espacio si no es texto
            self._case_chk.grid_forget()

        # Botones
        ttk.Button(self, text="Aplicar", style="Accent.TButton",
                   command=self._apply_click).grid(row=0, column=5, padx=(8, 4))
        ttk.Button(self, text="Limpiar",
                   command=self._clear_click).grid(row=0, column=6, padx=(4, 0))

        # Mensaje de error
        self._err_lbl = ttk.Label(self, textvariable=self._err, style="DangerBadge.TLabel")
        self._err_lbl.grid(row=1, column=0, columnspan=7, sticky="w", pady=(6, 0))
        self._err_lbl.grid_remove()

        # Default op
        self._op.set(ops[0])
        self._bind_enter_to_apply()

    # ----------------------------- Interacción ----------------------------- #

    def _bind_enter_to_apply(self) -> None:
        for w in (self._op_cb, self._v1_widget, self._v2_widget):
            w.bind("<Return>", lambda e: self._apply_click())

    def _on_op_change(self, *_):
        op = self._op.get()
        self._err_set("")
        # Mostrar/ocultar value2
        needs_v2 = (op == "entre")
        if needs_v2:
            self._v2_widget.grid()
        else:
            self._v2_widget.grid_remove()

        # Deshabilitar entradas en 'vacío/no vacío/hoy/esta semana/este mes'
        disable_all = op in {"vacío", "no vacío", "hoy", "esta semana", "este mes"}
        state = "disabled" if disable_all else "normal"
        try:
            self._v1_widget.configure(state=state)
            self._v2_widget.configure(state=state)
        except tk.TclError:
            pass

    def _err_set(self, msg: str):
        self._err.set(msg)
        if msg:
            self._err_lbl.grid()
        else:
            self._err_lbl.grid_remove()

    def _apply_click(self):
        desc = self.get_descriptor()
        if desc is None:
            return
        if self.on_apply:
            self.on_apply(desc)

    def _clear_click(self):
        self._v1.set("")
        self._v2.set("")
        self._err_set("")
        if self.on_clear:
            self.on_clear()

    # ----------------------------- API pública ----------------------------- #

    def get_descriptor(self) -> Optional[FilterDescriptor]:
        """Valida y construye el descriptor del filtro actual. Si hay error, lo muestra y retorna None."""
        op = self._op.get()
        v1 = self._v1.get().strip()
        v2 = self._v2.get().strip()

        # Validación según tipo
        try:
            if self.field_type == "number":
                if op == "entre":
                    _ = parse_number(v1)
                    _ = parse_number(v2)
                elif op not in {"vacío", "no vacío"}:
                    _ = parse_number(v1)
            elif self.field_type == "date":
                if op == "entre":
                    _ = parse_date(v1)
                    _ = parse_date(v2)
                elif op in {"hoy", "esta semana", "este mes", "vacío", "no vacío"}:
                    pass
                else:
                    _ = parse_date(v1)
            else:  # text
                if op in {"vacío", "no vacío"}:
                    pass
                else:
                    if not v1:
                        raise ValueError("Ingrese un valor")
        except ValueError as ex:
            self._err_set(str(ex))
            return None

        self._err_set("")
        return FilterDescriptor(
            field_name=self.field_name,
            field_type=self.field_type,
            op=op,
            value1=v1 or None,
            value2=v2 or None,
            case_sensitive=self._case.get(),
        )

    # ------------------------ Predicado (en memoria) ----------------------- #

    def make_predicate(self, extractor: Callable[[Any], Any]) -> Callable[[Any], bool]:
        """
        Devuelve un predicado que puedes usar para filtrar filas en memoria.
        'extractor' recibe el objeto fila y retorna el valor de esta columna.
        """
        desc = self.get_descriptor()
        if desc is None:
            # Predicado que siempre pasa si hay error; el caller elige qué hacer
            return lambda _: True

        op = desc.op

        def to_text(x: Any) -> str:
            return "" if x is None else str(x)

        def to_num(x: Any) -> Optional[float]:
            if x is None or x == "":
                return None
            try:
                return float(str(x).replace(",", "."))
            except Exception:
                return None

        def to_date(x: Any) -> Optional[date]:
            if x is None or x == "":
                return None
            if isinstance(x, date):
                return x
            s = str(x)
            try:
                return parse_date(s)
            except ValueError:
                return None

        # Texto
        if desc.field_type == "text":
            cs = desc.case_sensitive
            pat1 = (desc.value1 or "")
            if not cs:
                pat1 = pat1.lower()

            def pred_text(val: Any) -> bool:
                s = to_text(val)
                s_cmp = s if cs else s.lower()

                if op == "contiene":
                    return pat1 in s_cmp
                if op == "no contiene":
                    return pat1 not in s_cmp
                if op == "=":
                    return s_cmp == pat1
                if op == "≠":
                    return s_cmp != pat1
                if op == "empieza con":
                    return s_cmp.startswith(pat1)
                if op == "termina con":
                    return s_cmp.endswith(pat1)
                if op == "vacío":
                    return s == ""
                if op == "no vacío":
                    return s != ""
                return True

            return lambda row: pred_text(extractor(row))

        # Número
        if desc.field_type == "number":
            if op in {"vacío", "no vacío"}:
                def pred_empty(val: Any) -> bool:
                    n = to_num(val)
                    return (n is None) if op == "vacío" else (n is not None)
                return lambda row: pred_empty(extractor(row))

            v1 = parse_number(desc.value1 or "0")
            if op == "entre":
                v2 = parse_number(desc.value2 or "0")
                lo, hi = sorted([v1, v2])

                def pred_between(val: Any) -> bool:
                    n = to_num(val)
                    return (n is not None) and (lo <= n <= hi)

                return lambda row: pred_between(extractor(row))

            def pred_num(val: Any) -> bool:
                n = to_num(val)
                if n is None:
                    return False
                if op == "=":
                    return n == v1
                if op == "≠":
                    return n != v1
                if op == ">":
                    return n > v1
                if op == "≥":
                    return n >= v1
                if op == "<":
                    return n < v1
                if op == "≤":
                    return n <= v1
                return True

            return lambda row: pred_num(extractor(row))

        # Fecha
        today = date.today()
        if desc.field_type == "date":
            if op == "vacío" or op == "no vacío":
                def pred_empty(val: Any) -> bool:
                    d = to_date(val)
                    return (d is None) if op == "vacío" else (d is not None)
                return lambda row: pred_empty(extractor(row))

            if op == "hoy":
                def pred_today(val: Any) -> bool:
                    d = to_date(val)
                    return d == today
                return lambda row: pred_today(extractor(row))

            if op == "esta semana":
                start, end = week_bounds(today)
                def pred_week(val: Any) -> bool:
                    d = to_date(val)
                    return (d is not None) and (start <= d <= end)
                return lambda row: pred_week(extractor(row))

            if op == "este mes":
                start, end = month_bounds(today)
                def pred_month(val: Any) -> bool:
                    d = to_date(val)
                    return (d is not None) and (start <= d <= end)
                return lambda row: pred_month(extractor(row))

            if op == "entre":
                d1 = parse_date(desc.value1 or "")
                d2 = parse_date(desc.value2 or "")
                lo, hi = sorted([d1, d2])

                def pred_between(val: Any) -> bool:
                    d = to_date(val)
                    return (d is not None) and (lo <= d <= hi)
                return lambda row: pred_between(extractor(row))

            # Comparadores simples
            dv = parse_date(desc.value1 or "")
            def pred_date(val: Any) -> bool:
                d = to_date(val)
                if d is None:
                    return False
                if op == "=":
                    return d == dv
                if op == "≠":
                    return d != dv
                if op == ">":
                    return d > dv
                if op == "≥":
                    return d >= dv
                if op == "<":
                    return d < dv
                if op == "≤":
                    return d <= dv
                return True

            return lambda row: pred_date(extractor(row))

        # Fallback
        return lambda _: True

    # --------------------------- SQL (sin ORM) ----------------------------- #

    def build_sql(self, column_name: str, *, driver: str = "sqlite") -> Tuple[str, List[Any]]:
        """
        Construye un fragmento SQL WHERE y su lista de parámetros.
        No agrega la palabra 'WHERE'; devuelve (sql, params).
        Soporta: sqlite, postgres, mysql (básico).

        Para campos texto usa case-insensitive por defecto (lower()).
        Para 'vacío' en texto: (col IS NULL OR col = '').
        Para 'vacío' en número/fecha: (col IS NULL).
        """
        desc = self.get_descriptor()
        if desc is None:
            return "1=1", []

        op = desc.op
        params: List[Any] = []

        # Helpers por driver
        def ilike(col: str) -> str:
            if desc.case_sensitive:
                return f"{col} LIKE ?"
            # Case-insensitive manual (portable)
            return f"LOWER({col}) LIKE LOWER(?)"

        # Texto
        if desc.field_type == "text":
            if op == "vacío":
                return f"({column_name} IS NULL OR {column_name} = '')", []
            if op == "no vacío":
                return f"({column_name} IS NOT NULL AND {column_name} <> '')", []

            v = desc.value1 or ""
            if op == "contiene":
                params.append(f"%{v}%")
                return ilike(column_name), params
            if op == "no contiene":
                params.append(f"%{v}%")
                return f"NOT ({ilike(column_name)})", params
            if op == "=":
                if desc.case_sensitive:
                    return f"{column_name} = ?", [v]
                return (f"LOWER({column_name}) = LOWER(?)", [v])
            if op == "≠":
                if desc.case_sensitive:
                    return f"{column_name} <> ?", [v]
                return (f"LOWER({column_name}) <> LOWER(?)", [v])
            if op == "empieza con":
                params.append(f"{v}%")
                return ilike(column_name), params
            if op == "termina con":
                params.append(f"%{v}")
                return ilike(column_name), params

        # Número
        if desc.field_type == "number":
            if op == "vacío":
                return f"{column_name} IS NULL", []
            if op == "no vacío":
                return f"{column_name} IS NOT NULL", []
            if op == "entre":
                a = parse_number(desc.value1 or "0")
                b = parse_number(desc.value2 or "0")
                lo, hi = sorted([a, b])
                params.extend([lo, hi])
                return f"{column_name} BETWEEN ? AND ?", params
            a = parse_number(desc.value1 or "0")
            if op == "=":
                return f"{column_name} = ?", [a]
            if op == "≠":
                return f"{column_name} <> ?", [a]
            if op == ">":
                return f"{column_name} > ?", [a]
            if op == "≥":
                return f"{column_name} >= ?", [a]
            if op == "<":
                return f"{column_name} < ?", [a]
            if op == "≤":
                return f"{column_name} <= ?", [a]

        # Fecha
        if desc.field_type == "date":
            if op == "vacío":
                return f"{column_name} IS NULL", []
            if op == "no vacío":
                return f"{column_name} IS NOT NULL", []
            if op == "hoy":
                d = date.today().isoformat()
                return f"DATE({column_name}) = DATE(?)", [d]
            if op == "esta semana":
                s, e = week_bounds(date.today())
                return f"DATE({column_name}) BETWEEN DATE(?) AND DATE(?)", [s.isoformat(), e.isoformat()]
            if op == "este mes":
                s, e = month_bounds(date.today())
                return f"DATE({column_name}) BETWEEN DATE(?) AND DATE(?)", [s.isoformat(), e.isoformat()]
            if op == "entre":
                d1 = parse_date(desc.value1 or "").isoformat()
                d2 = parse_date(desc.value2 or "").isoformat()
                lo, hi = sorted([d1, d2])
                return f"DATE({column_name}) BETWEEN DATE(?) AND DATE(?)", [lo, hi]
            # comparadores simples
            d1 = parse_date(desc.value1 or "").isoformat()
            if op == "=":
                return f"DATE({column_name}) = DATE(?)", [d1]
            if op == "≠":
                return f"DATE({column_name}) <> DATE(?)", [d1]
            if op == ">":
                return f"DATE({column_name}) > DATE(?)", [d1]
            if op == "≥":
                return f"DATE({column_name}) >= DATE(?)", [d1]
            if op == "<":
                return f"DATE({column_name}) < DATE(?)", [d1]
            if op == "≤":
                return f"DATE({column_name}) <= DATE(?)", [d1]

        # Fallback
        return "1=1", []

