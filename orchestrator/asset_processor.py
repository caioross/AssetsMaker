"""
asset_processor.py — pós-processamento dos PNGs gerados pelo ComfyUI.

Pipeline:
1. Recebe PNG cru (bytes ou path)
2. Remove fundo via rembg (com sessão persistente para performance)
3. Faz crop pelo bounding box do alpha (remove margens vazias)
4. Padding opcional, resize se necessário
5. Salva no path final
6. (Opcional) compõe spritesheet a partir de frames de animação

Performance:
- rembg cria a sessão uma vez e reusa — primeira geração leva ~2s pra carregar
  o modelo, próximas ficam em <500ms cada.
- Modelo padrão: `birefnet-general` (bom em sprites com fundo qualquer).
  Para sprites com fundo já limpo, `u2net` é mais rápido mas menos preciso.
"""
from __future__ import annotations

import io
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Iterable

from PIL import Image


_REMBG_SESSION = None  # singleton lazy

DEFAULT_REMBG_MODEL = "birefnet-general"
# Modelos alternativos disponíveis na rembg: u2net, u2netp, silueta, isnet-general-use, birefnet-general, birefnet-portrait


def _get_rembg_session(model_name: str = DEFAULT_REMBG_MODEL):
    global _REMBG_SESSION
    if _REMBG_SESSION is None:
        from rembg import new_session
        _REMBG_SESSION = new_session(model_name)
    return _REMBG_SESSION


# ============================================================================
# Operações principais
# ============================================================================

def remove_background(png_bytes: bytes, *, model: str = DEFAULT_REMBG_MODEL) -> bytes:
    """Roda rembg sobre os bytes do PNG e retorna PNG transparente."""
    from rembg import remove
    session = _get_rembg_session(model)
    return remove(png_bytes, session=session)


def crop_to_content(img: Image.Image, *, padding: int = 8) -> Image.Image:
    """Recorta a imagem ao bounding box do alpha não-transparente, com padding."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = img.split()[-1]
    bbox = alpha.getbbox()
    if bbox is None:
        return img  # imagem 100% transparente, retorna como está
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - padding)
    y0 = max(0, y0 - padding)
    x1 = min(img.width, x1 + padding)
    y1 = min(img.height, y1 + padding)
    return img.crop((x0, y0, x1, y1))


def resize_keep_aspect(img: Image.Image, *, max_side: int) -> Image.Image:
    if max(img.size) <= max_side:
        return img
    img = img.copy()
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return img


def power_of_two_pad(img: Image.Image, fill=(0, 0, 0, 0)) -> Image.Image:
    """Faz padding até a próxima potência de 2 (útil para engines que exigem isso)."""
    def next_pow2(n: int) -> int:
        return 1 << (n - 1).bit_length()

    w, h = img.size
    target_w, target_h = next_pow2(w), next_pow2(h)
    if (target_w, target_h) == (w, h):
        return img
    canvas = Image.new("RGBA", (target_w, target_h), fill)
    canvas.paste(img, ((target_w - w) // 2, (target_h - h) // 2))
    return canvas


# ============================================================================
# Pipeline completo de finalização
# ============================================================================

@dataclass
class FinalizeOptions:
    remove_bg: bool = True
    rembg_model: str = DEFAULT_REMBG_MODEL
    crop: bool = True
    crop_padding: int = 8
    max_side: Optional[int] = None  # None = não redimensiona
    power_of_two: bool = False


def finalize_asset(
    png_bytes: bytes,
    target_path: Path,
    options: Optional[FinalizeOptions] = None,
) -> Path:
    """
    Aplica o pipeline completo ao PNG cru e salva em target_path.
    """
    opts = options or FinalizeOptions()
    if opts.remove_bg:
        png_bytes = remove_background(png_bytes, model=opts.rembg_model)

    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    if opts.crop:
        img = crop_to_content(img, padding=opts.crop_padding)
    if opts.max_side:
        img = resize_keep_aspect(img, max_side=opts.max_side)
    if opts.power_of_two:
        img = power_of_two_pad(img)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(target_path, "PNG", optimize=True)
    return target_path


# ============================================================================
# Spritesheet / atlas
# ============================================================================

@dataclass
class AtlasFrame:
    name: str
    x: int
    y: int
    w: int
    h: int


def build_atlas(
    frames: Iterable[Path],
    atlas_png_path: Path,
    *,
    columns: int = 8,
    cell_size: Optional[tuple[int, int]] = None,
    background=(0, 0, 0, 0),
) -> dict:
    """
    Monta um spritesheet a partir de PNGs individuais.

    Se cell_size for None, usa o tamanho do maior frame (centralizando os menores).
    Retorna metadata-dict (também salva como <atlas_png_path>.json).
    """
    frames = list(frames)
    if not frames:
        raise ValueError("Nenhum frame para montar atlas.")

    images = [Image.open(p).convert("RGBA") for p in frames]

    if cell_size is None:
        cw = max(im.width for im in images)
        ch = max(im.height for im in images)
    else:
        cw, ch = cell_size

    rows = math.ceil(len(images) / columns)
    atlas = Image.new("RGBA", (columns * cw, rows * ch), background)

    metadata = {
        "image": atlas_png_path.name,
        "columns": columns,
        "rows": rows,
        "frame_width": cw,
        "frame_height": ch,
        "frames": []
    }

    for idx, (path, im) in enumerate(zip(frames, images)):
        col = idx % columns
        row = idx // columns
        # Centraliza o sprite na célula
        x_off = col * cw + (cw - im.width) // 2
        y_off = row * ch + (ch - im.height) // 2
        atlas.paste(im, (x_off, y_off), im)
        metadata["frames"].append({
            "name": path.stem,
            "x": col * cw,
            "y": row * ch,
            "w": cw,
            "h": ch,
        })

    atlas_png_path.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(atlas_png_path, "PNG", optimize=True)
    json_path = atlas_png_path.with_suffix(".json")
    json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


# ============================================================================
# Helpers de naming
# ============================================================================

DIRECTION_NAMES = ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]


def frame_filename(
    base_name: str,
    *,
    animation: str,
    direction_idx: int,
    frame_idx: int,
) -> str:
    """Padroniza nomes de frames: berserker_idle_NE_003.png"""
    direction = DIRECTION_NAMES[direction_idx % len(DIRECTION_NAMES)]
    return f"{base_name}_{animation}_{direction}_{frame_idx:03d}.png"
