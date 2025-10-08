# src/utils/image_store.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Tuple
import shutil, uuid
from PIL import Image

MEDIA_ROOT = Path("app_data/media").resolve()
PRODUCTS_DIR = MEDIA_ROOT / "products"
THUMB_SIZE = (256, 256)

def _ensure_dirs() -> None:
    PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)

def product_dir(product_id: int) -> Path:
    _ensure_dirs()
    p = PRODUCTS_DIR / str(product_id)
    p.mkdir(parents=True, exist_ok=True)
    return p

def save_image_for_product(product_id: int, source_path: Path) -> Tuple[Path, Path]:
    """Copia la imagen y genera thumbnail JPG. Retorna (ruta, ruta_thumbnail)."""
    pdir = product_dir(product_id)
    ext = (source_path.suffix or ".jpg").lower()
    dest = pdir / f"{uuid.uuid4().hex}{ext}"
    shutil.copy2(source_path, dest)

    thumb = pdir / f"{dest.stem}_thumb.jpg"
    with Image.open(dest) as im:
        im = im.convert("RGB")
        im.thumbnail(THUMB_SIZE)
        im.save(thumb, "JPEG", quality=88)

    return dest, thumb

def get_latest_image_paths(product_id: int) -> Tuple[Optional[Path], Optional[Path]]:
    """Devuelve (imagen_principal, thumbnail) más recientes o (None, None)."""
    pdir = product_dir(product_id)
    imgs = sorted(pdir.glob("*.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not imgs: return None, None
    main = imgs[0]
    thumb = pdir / f"{main.stem}_thumb.jpg"
    return main, (thumb if thumb.exists() else None)
