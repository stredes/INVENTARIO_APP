from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from src.gui.products_view import calcular_precios
from src.gui.suppliers_view import validar_rut_chileno
from src.gui.sql_importer_dialog import (
    _split_sql,
    _normalize_sql,
    _statement_preview,
    detect_destructive_statements,
)
from src.gui.widgets.autocomplete_combobox import _norm
from src.gui.widgets.column_filter import (
    parse_date,
    parse_number,
    week_bounds,
    month_bounds,
)
from src.gui.printer_select_dialog import _list_printers
from src.data.database import get_engine
from src.data.models import Supplier, Product


# ---------------------- Unit tests: pure helpers ---------------------- #

def test_calcular_precios_rounds_expected_values():
    """ProductsView helper should round IVA/venta totals consistently."""
    monto_iva, precio_mas_iva, precio_venta = calcular_precios(
        pc=1234.56,
        iva=19.0,
        margen=35.0,
    )
    assert monto_iva == 235
    assert precio_mas_iva == 1469
    assert precio_venta == 1983


@pytest.mark.parametrize(
    "rut,expected",
    [
        ("12.345.678-5", True),
        ("12.345.678-k", True),  # dígito verificador K en minúscula
        ("12345678", False),
        ("sin-guion", False),
        ("", False),
    ],
)
def test_validar_rut_chileno_formats(rut: str, expected: bool):
    assert validar_rut_chileno(rut) is expected


def test_norm_removes_accents_and_lowercases():
    assert _norm("ÁÉÍÓÚ Ñ 123") == "aeiou n 123"
    assert _norm(None) == ""


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2024-05-10", date(2024, 5, 10)),
        ("10/05/2024", date(2024, 5, 10)),
        ("10-05-24", date(2024, 5, 10)),
    ],
)
def test_parse_date_accepts_common_formats(raw: str, expected: date):
    assert parse_date(raw) == expected


def test_parse_date_rejects_invalid_format():
    with pytest.raises(ValueError):
        parse_date("31-02-2024")


def test_parse_number_supports_comma_decimal():
    assert parse_number("123,45") == pytest.approx(123.45)
    with pytest.raises(ValueError):
        parse_number(None)  # type: ignore[arg-type]


def test_week_and_month_bounds_cover_expected_ranges():
    start_week, end_week = week_bounds(date(2024, 5, 8))  # Wednesday
    assert start_week == date(2024, 5, 6)  # Monday
    assert end_week == date(2024, 5, 12)   # Sunday

    start_month, end_month = month_bounds(date(2023, 12, 15))
    assert start_month == date(2023, 12, 1)
    assert end_month == date(2023, 12, 31)


def test_split_sql_handles_comments_and_quoted_semicolons():
    script = """
    -- Comentario debe ser ignorado
    INSERT INTO dummy VALUES ('texto; con ; punto y coma');
    INSERT INTO dummy VALUES ("dobles; tambien");
    """
    stmts = _split_sql(script)
    assert len(stmts) == 2
    assert "texto; con ; punto y coma" in stmts[0]
    assert "dobles; tambien" in stmts[1]


def test_normalize_sql_trims_and_removes_bom():
    raw = "\ufeffINSERT INTO x VALUES (1);\r\n\r\n"
    assert _normalize_sql(raw) == "INSERT INTO x VALUES (1);"


def test_statement_preview_shortens_long_statements():
    stmt = "INSERT INTO demo VALUES (" + ",".join(str(i) for i in range(50)) + ");"
    preview = _statement_preview(stmt, max_len=40)
    assert preview.endswith("...")
    assert len(preview) == 40


def test_list_printers_prefers_win32_api(monkeypatch):
    from src.gui import printer_select_dialog as psd

    dummy_entries = [
        ("", "", "HP-Laser"),
        ("", "", "BROTHER 2240"),
    ]

    class DummyWin32:
        @staticmethod
        def EnumPrinters(level: int):
            assert level == 2
            return dummy_entries

    monkeypatch.setattr(psd, "win32print", DummyWin32, raising=False)
    monkeypatch.setattr(psd, "sys", SimpleNamespace(platform="win32"), raising=False)
    assert _list_printers() == ["HP-Laser", "BROTHER 2240"]


def test_list_printers_uses_lpstat_on_unix(monkeypatch):
    from src.gui import printer_select_dialog as psd

    sample = "printer HP_DeskJet is idle\nprinter Zebra status\n"

    monkeypatch.setattr(psd, "win32print", None, raising=False)
    monkeypatch.setattr(psd, "sys", SimpleNamespace(platform="linux"), raising=False)
    monkeypatch.setattr(psd.subprocess, "check_output", lambda *a, **k: sample)

    assert _list_printers() == ["HP_DeskJet", "Zebra"]


def test_detect_destructive_statements_flags_schema_changes():
    stmts = [
        "INSERT INTO suppliers (razon_social) VALUES ('A');",
        "DROP TABLE suppliers;",
        "ALTER TABLE products ADD COLUMN foo TEXT;",
    ]
    flagged = detect_destructive_statements(stmts)
    assert len(flagged) == 2
    assert any("drop table" in s.lower() for s in flagged)
    assert any("alter table" in s.lower() for s in flagged)


def test_detect_destructive_statements_allows_safe_statements():
    stmts = [
        "INSERT INTO suppliers (razon_social) VALUES ('A');",
        "UPDATE products SET precio_venta = 1000 WHERE id = 1;",
    ]
    assert detect_destructive_statements(stmts) == []


# ---------------------- Integration-style test ---------------------- #

def test_split_sql_executes_against_database(session):
    """
    Ejecuta un script SQL completo contra la BD temporal usando el helper del
    importador masivo y verifica que los registros queden disponibles vía ORM.
    """
    script = """
    -- Carga proveedor con comentario
    INSERT INTO suppliers (razon_social, rut, contacto)
    VALUES ('Importadora; Uno', '76.199.199-1', 'Ventas');

    -- Producto asociado; se refiere al proveedor anterior
    INSERT INTO products (nombre, sku, precio_compra, precio_venta, stock_actual,
                          unidad_medida, id_proveedor)
    VALUES ('Kit \"Multi;uso\"', 'PX-TEST', 1000, 1500, 5, 'unidad',
            (SELECT id FROM suppliers WHERE rut = '76.199.199-1'));
    """

    engine = get_engine()
    with engine.begin() as conn:
        for stmt in _split_sql(script):
            conn.exec_driver_sql(stmt)

    session.expire_all()
    supplier = session.query(Supplier).filter_by(rut="76.199.199-1").one()
    product = session.query(Product).filter_by(sku="PX-TEST").one()

    assert product.id_proveedor == supplier.id
    assert int(product.stock_actual) == 5
