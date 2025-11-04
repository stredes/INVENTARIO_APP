from __future__ import annotations

import re
from pathlib import Path


MAPPING = {
    # General words
    "Catǭlogo": "Catálogo",
    "catǭlogo": "catálogo",
    "T��tulo": "Título",
    "Dise��o": "Diseño",
    "diǭlogo": "diálogo",
    "menǧ": "menú",
    "C�digo": "Código",
    "v�a": "vía",
    "est�": "está",
    "Ubicaci�n": "Ubicación",
    "Recepci�n": "Recepción",
    "�rdenes": "Órdenes",
    "N�": "N°",
    "Gu��a": "Guía",
    "Raz��n": "Razón",
    "Direcci��n": "Dirección",
    "TelǸfono": "Teléfono",
    "L�mites": "Límites",
    "M�nimo": "Mínimo",
    "M�ximo": "Máximo",
    "Dilogo": "Diálogo",
    "dilogo": "diálogo",
    "Catlogo": "Catálogo",
    "Conexi��n": "Conexión",
    "Impresi�n": "Impresión",
    "Ordenes": "Órdenes",
    # Common messages
    "inv�lida": "inválida",
    "No se encontr�": "No se encontró",
    "Venc.": "Venc.",  # keep as is but ensure mapping doesn't break
    # UTF-8 mis-decoded sequences
    "Ã¡": "á", "Ã©": "é", "Ã­": "í", "Ã³": "ó", "Ãº": "ú",
    "Ã": "Ñ", "Ã±": "ñ", "Ã2": "Œ",
    "Ã0": "’", "Â": "",  # stray NO-BREAK SPACE marker from cp1252
}


def fix_text(s: str) -> str:
    for bad, good in MAPPING.items():
        s = s.replace(bad, good)
    # Fix stray sequences where '�' appears before quotes in Órdenes tab
    s = s.replace('"rdenes', 'Órdenes')
    return s


def main() -> None:
    root = Path('src')
    if not root.exists():
        return
    files = list(root.rglob('*.py'))
    changed = []
    for f in files:
        txt = f.read_text(encoding='utf-8', errors='replace')
        fixed = fix_text(txt)
        if fixed != txt:
            f.write_text(fixed, encoding='utf-8')
            changed.append(f)
    print(f"Patched {len(changed)} files:")
    for f in changed:
        print(" -", f)


if __name__ == '__main__':
    main()
