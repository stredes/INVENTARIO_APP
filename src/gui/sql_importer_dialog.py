from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List

from src.data.database import get_engine


def _split_sql(sql: str) -> list[str]:
    """Split a SQL script into individual statements.
    - Removes line comments starting with '--'.
    - Splits on ';' outside of quotes (simple heuristic).
    Good enough for typical INSERT/UPDATE batches.
    """
    cleaned: list[str] = []
    in_single = False
    in_double = False
    buf: list[str] = []
    for raw_line in sql.splitlines():
        line = raw_line.rstrip()
        if not in_single and not in_double:
            if line.lstrip().startswith("--"):
                continue
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "'" and not in_double:
                in_single = not in_single
                buf.append(ch)
            elif ch == '"' and not in_single:
                in_double = not in_double
                buf.append(ch)
            elif ch == ";" and not in_single and not in_double:
                stmt = "".join(buf).strip()
                if stmt:
                    cleaned.append(stmt)
                buf = []
            else:
                buf.append(ch)
            i += 1
        buf.append("\n")
    tail = "".join(buf).strip()
    if tail:
        cleaned.append(tail)
    return cleaned


def _normalize_sql(sql: str) -> str:
    """Normaliza saltos de línea y elimina BOM/espacios residuales."""
    if not sql:
        return ""
    cleaned = sql.replace("\r\n", "\n").replace("\r", "\n")
    if cleaned.startswith("\ufeff"):
        cleaned = cleaned.lstrip("\ufeff")
    return cleaned.strip()


def _statement_preview(stmt: str, max_len: int = 160) -> str:
    """Devuelve una versión resumida en una sola línea para mostrar en errores."""
    text = " ".join(stmt.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


_PROHIBITED_KEYWORDS = (
    "drop ",
    "alter ",
    "create table",
    "create trigger",
    "attach ",
    "detach ",
    "vacuum",
    "pragma ",
)


def detect_destructive_statements(statements: List[str]) -> List[str]:
    """
    Returns the subset of statements that appear to contain destructive keywords.
    The check is case-insensitive and aims to block schema-altering commands.
    """
    flagged: List[str] = []
    for stmt in statements:
        low = stmt.lower()
        if any(keyword in low for keyword in _PROHIBITED_KEYWORDS):
            flagged.append(stmt.strip())
    return flagged


TEMPLATES: Dict[str, List[List[str]]] = {
    # columnas: [nombre_columna, tipo/ejemplo, notas]
    "suppliers": [
        ["razon_social", "TEXT", "Obligatorio"],
        ["rut", "TEXT", "Obligatorio, unico"],
        ["contacto", "TEXT", "Opcional"],
        ["telefono", "TEXT", "Opcional"],
        ["email", "TEXT", "Opcional"],
        ["direccion", "TEXT", "Opcional"],
    ],
    "products": [
        ["nombre", "TEXT", "Obligatorio"],
        ["sku", "TEXT", "Obligatorio, unico"],
        ["precio_compra", "NUMERIC(12,2)", "Obligatorio (neto)"],
        ["precio_venta", "NUMERIC(12,2)", "Obligatorio"],
        ["stock_actual", "INTEGER", "Default 0"],
        ["unidad_medida", "TEXT", "Opcional (p.ej. 'unidad','lt','kg')"],
        ["id_proveedor", "INTEGER", "FK suppliers.id (recomendado)"],
        ["id_ubicacion", "INTEGER", "FK locations.id (opcional)"],
        ["image_path", "TEXT", "Opcional"],
        ["barcode", "TEXT", "Opcional"],
    ],
    "customers": [
        ["razon_social", "TEXT", "Obligatorio"],
        ["rut", "TEXT", "Obligatorio, unico"],
        ["contacto", "TEXT", "Opcional"],
        ["telefono", "TEXT", "Opcional"],
        ["email", "TEXT", "Opcional"],
        ["direccion", "TEXT", "Opcional"],
    ],
    "locations": [
        ["nombre", "TEXT", "Obligatorio, unico"],
        ["descripcion", "TEXT", "Opcional"],
    ],
}


EXAMPLES: Dict[str, str] = {
    "general": """
-- Planilla general: proveedores, ubicaciones, productos y clientes

-- 1) Proveedores
INSERT INTO suppliers (razon_social, rut, contacto, telefono, direccion) VALUES
  ('PROV EJEMPLO SPA', '76.999.999-9', 'Ventas', '+56 2 1234567', 'Santiago');

-- 2) Ubicaciones
INSERT INTO locations (nombre, descripcion) VALUES
  ('Bodega Central', 'Principal');

-- 3) Productos (relacionados al proveedor anterior y ubicacion)
INSERT INTO products (nombre, sku, precio_compra, precio_venta, stock_actual, unidad_medida, id_proveedor, id_ubicacion)
VALUES
  ('DETERGENTE 3 LT', 'DET-3LT', 4252, 6500, 10, 'lt 3', (SELECT id FROM suppliers WHERE rut='76.999.999-9'), (SELECT id FROM locations WHERE nombre='Bodega Central')),
  ('PAPEL HIG 4 ROLLOS', 'PH-4R', 1397, 2300, 24, 'bolsa x 4', (SELECT id FROM suppliers WHERE rut='76.999.999-9'), (SELECT id FROM locations WHERE nombre='Bodega Central'));

-- 4) Clientes
INSERT INTO customers (razon_social, rut, contacto, telefono, direccion) VALUES
  ('Cliente Uno SpA', '77.111.111-1', 'Carla', '+56 9 98765432', 'Nunoa');
""",
    "products": """
-- Ejemplo: inserta proveedor y luego productos
INSERT INTO suppliers (razon_social, rut, contacto, telefono)
VALUES ('PROV EJEMPLO SPA', '76.999.999-9', 'Ventas', '+56 2 1234567');

-- Usa el id del proveedor recien creado
INSERT INTO products (nombre, sku, precio_compra, precio_venta, stock_actual, unidad_medida, id_proveedor)
VALUES
  ('DETERGENTE 3 LT', 'DET-3LT', 4252, 6500, 10, 'lt 3', (SELECT id FROM suppliers WHERE rut='76.999.999-9')),
  ('PAPEL HIG 4 ROLLOS', 'PH-4R', 1397, 2300, 24, 'bolsa x 4', (SELECT id FROM suppliers WHERE rut='76.999.999-9'));
""",
    "suppliers": """
-- Inserta varios proveedores
INSERT INTO suppliers (razon_social, rut, contacto, telefono, direccion) VALUES
  ('ACME S.A.', '76.111.111-1', 'Juan', '+56 2 1111111', 'Santiago'),
  ('FOO BAR LTDA.', '76.222.222-2', 'Maria', '+56 2 2222222', 'Providencia');
""",
    "customers": """
-- Inserta varios clientes
INSERT INTO customers (razon_social, rut, contacto, telefono, direccion) VALUES
  ('Cliente Uno SpA', '77.111.111-1', 'Carla', '+56 9 98765432', 'Nunoa'),
  ('Cliente Dos Ltda', '77.222.222-2', 'Pedro', '+56 2 3456789', 'Maipu');
""",
    "locations": """
-- Inserta ubicaciones
INSERT INTO locations (nombre, descripcion) VALUES
  ('Bodega Central', 'Principal'),
  ('Mostrador', 'Despacho y venta');
""",
}

class SqlMassImporter(tk.Toplevel):
    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.title("Importacion SQL masiva")
        self.geometry("900x600")
        self.transient(master)
        self.grab_set()

        # Top controls
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Plantilla:").pack(side="left")
        # Agregamos 'general' como opción por defecto que incluye TODAS las tablas
        all_opts = ["general"] + list(TEMPLATES.keys())
        self.var_tpl = tk.StringVar(value="general")
        cmb = ttk.Combobox(top, textvariable=self.var_tpl, values=all_opts, width=18, state="readonly")
        cmb.pack(side="left", padx=6)
        ttk.Button(top, text="Cargar ejemplo", command=self._load_example).pack(side="left", padx=6)

        body = ttk.PanedWindow(self, orient="vertical")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Planilla (columnas esperadas)
        frm_plan = ttk.Labelframe(body, text="Planilla de columnas (referencia)")
        # Incluimos columna 'Tabla' para la planilla general
        self.tv = ttk.Treeview(frm_plan, columns=("tabla", "col", "tipo", "nota"), show="headings", height=8)
        self.tv.heading("tabla", text="Tabla")
        self.tv.heading("col", text="Columna")
        self.tv.heading("tipo", text="Tipo/Ejemplo")
        self.tv.heading("nota", text="Notas")
        self.tv.column("tabla", width=120)
        self.tv.column("col", width=180)
        self.tv.column("tipo", width=160)
        self.tv.column("nota", width=360)
        self.tv.pack(fill="both", expand=True, padx=6, pady=6)
        self._refresh_planilla()
        body.add(frm_plan, weight=1)

        # SQL editor
        frm_sql = ttk.Labelframe(body, text="SQL a ejecutar (se ejecuta dentro de una transaccion)")
        self.txt = tk.Text(frm_sql, wrap="none", height=12)
        self.txt.pack(fill="both", expand=True, padx=6, pady=6)
        body.add(frm_sql, weight=2)

        # Buttons
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btns, text="Ejecutar SQL", command=self._execute).pack(side="right")
        ttk.Button(btns, text="Cerrar", command=self.destroy).pack(side="right", padx=6)

        cmb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_planilla())

    def _refresh_planilla(self):
        tpl = self.var_tpl.get()
        self.tv.delete(*self.tv.get_children())
        if tpl == "general":
            for table, rows in TEMPLATES.items():
                for col, tipo, nota in rows:
                    self.tv.insert("", "end", values=[table, col, tipo, nota])
        else:
            for col, tipo, nota in TEMPLATES.get(tpl, []):
                self.tv.insert("", "end", values=[tpl, col, tipo, nota])

    def _load_example(self):
        tpl = self.var_tpl.get()
        ex = EXAMPLES.get(tpl, EXAMPLES.get("general", ""))
        if not ex:
            return
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", ex)

    def _execute(self):
        raw_sql = self.txt.get("1.0", "end")
        sql = _normalize_sql(raw_sql)
        if not sql:
            messagebox.showwarning("SQL", "Ingrese codigo SQL para ejecutar." , parent=self)
            return
        statements = [stmt for stmt in _split_sql(sql) if stmt.strip()]
        if not statements:
            messagebox.showwarning("SQL", "No se detectaron sentencias SQL válidas.", parent=self)
            return
        flagged = detect_destructive_statements(statements)
        if flagged:
            sample = "\n\n".join(flagged[:3])
            messagebox.showerror(
                "SQL",
                "Por seguridad, se bloquearon comandos potencialmente destructivos "
                "(DROP/ALTER/CREATE/ATTACH/DETACH/PRAGMA/VACUUM).\n\n"
                f"Revise las sentencias:\n{sample}",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Confirmar importación",
            f"Se ejecutarán {len(statements)} sentencias SQL.\n"
            "Asegúrese de tener un respaldo antes de continuar.\n\n"
            "¿Desea continuar?",
            parent=self,
        ):
            return
        eng = get_engine()
        try:
            with eng.begin() as conn:
                try:
                    is_sqlite = getattr(getattr(eng, "dialect", None), "name", "") == "sqlite"
                except Exception:
                    is_sqlite = False
                if is_sqlite:
                    try:
                        conn.exec_driver_sql("PRAGMA foreign_keys=ON;")
                    except Exception:
                        pass
                for idx, stmt in enumerate(statements, start=1):
                    try:
                        conn.exec_driver_sql(stmt)
                    except Exception as ex:
                        preview = _statement_preview(stmt)
                        raise RuntimeError(
                            f"Error en sentencia #{idx}:\n{preview}\n\nDetalle: {ex}"
                        ) from ex
            messagebox.showinfo("SQL", "Ejecucion completada.", parent=self)
        except Exception as ex:
            messagebox.showerror("SQL", f"Error al ejecutar:\n{ex}", parent=self)


__all__ = [
    "SqlMassImporter",
    "_split_sql",
    "_normalize_sql",
    "_statement_preview",
    "detect_destructive_statements",
]





