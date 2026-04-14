from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook


class ExportService:
    @staticmethod
    def export_to_csv(file_path: str | Path, headers: list[str], rows: Iterable[Iterable]) -> None:
        with open(file_path, "w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(headers)
            writer.writerows(rows)

    @staticmethod
    def export_to_excel(file_path: str | Path, sheet_name: str, headers: list[str], rows: Iterable[Iterable]) -> None:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = sheet_name
        worksheet.append(headers)
        for row in rows:
            worksheet.append(list(row))
        for column_cells in worksheet.columns:
            max_length = 0
            column_letter = column_cells[0].column_letter
            for cell in column_cells:
                max_length = max(max_length, len(str(cell.value or "")))
            worksheet.column_dimensions[column_letter].width = min(max_length + 2, 40)
        workbook.save(file_path)
