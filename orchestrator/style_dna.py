"""
style_dna.py — extrai, persiste e mantém o DNA visual de cada projeto.

Fluxo:
1. Usuário joga imagens em projects/<game>/references/
2. extract_from_references() lê todas, faz análise computacional (paleta, contraste,
   etc.) e devolve um StyleDNA *parcial* (campos visuais preenchidos).
3. O LLM diretor (Claude Code ou Ollama) completa com tokens textuais, escolha de
   LoRAs e configs de câmera.
4. save() persiste em style_dna.json.

A análise computacional é deliberadamente conservadora: prefere extrair fatos
(paleta dominante, contraste, etc.) que o LLM julga semanticamente, em vez de
chutar tags semânticas que podem estar erradas.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

from .schemas import ColorEntry, LightingProfile, SilhouetteProfile, StyleDNA


# Caminhos relativos à raiz do projeto (passados como Path)
DNA_FILENAME = "style_dna.json"


# ============================================================================
# Análise computacional de uma imagem
# ============================================================================

def _load_image_rgb(path: Path, max_side: int = 512) -> np.ndarray:
    """Carrega imagem como array numpy RGB normalizado, redimensionada para análise."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return np.asarray(img)


def extract_palette(images: list[np.ndarray], n_colors: int = 8) -> list[ColorEntry]:
    """
    Agrega todos os pixels das imagens e extrai paleta por KMeans em RGB.

    Retorna cores ordenadas por dominância. Para projetos sérios, dá pra
    migrar pra LAB para distâncias perceptuais mais corretas, mas RGB já entrega
    paletas úteis na prática.
    """
    all_pixels = np.concatenate([img.reshape(-1, 3) for img in images], axis=0)
    # Amostra para acelerar
    if all_pixels.shape[0] > 50_000:
        idx = np.random.RandomState(42).choice(all_pixels.shape[0], 50_000, replace=False)
        all_pixels = all_pixels[idx]

    kmeans = KMeans(n_clusters=n_colors, n_init=4, random_state=42)
    labels = kmeans.fit_predict(all_pixels)
    centers = kmeans.cluster_centers_.astype(int)

    # Peso = fração de pixels atribuídos
    counts = np.bincount(labels, minlength=n_colors)
    weights = counts / counts.sum()

    # Ordena por peso desc
    order = np.argsort(-weights)
    palette = []
    for i in order:
        r, g, b = centers[i]
        palette.append(ColorEntry(
            hex=f"#{r:02X}{g:02X}{b:02X}",
            weight=float(weights[i]),
        ))
    return palette


def estimate_lighting(images: list[np.ndarray]) -> LightingProfile:
    """
    Heurística simples: olha o histograma de luminância para inferir o perfil de luz.

    - Histograma bimodal (muito escuro + muito claro): dramatic_rim / noir_lowkey
    - Histograma centralizado e largo: soft_diffuse
    - Histograma com pico médio: painterly_flat
    """
    lums = []
    rim_scores = []
    for img in images:
        lum = (0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]) / 255.0
        lums.append(lum.flatten())
        # rim_score = fração de pixels muito claros adjacentes a pixels muito escuros
        edges_bright = (lum > 0.85)
        edges_dark = (lum < 0.15)
        # convolução simples
        from scipy.ndimage import binary_dilation
        try:
            dilated_dark = binary_dilation(edges_dark, iterations=2)
            rim_pixels = edges_bright & dilated_dark
            rim_scores.append(rim_pixels.mean())
        except Exception:
            rim_scores.append(0.0)

    all_lum = np.concatenate(lums)
    mean = all_lum.mean()
    std = all_lum.std()
    # Bimodalidade aproximada
    hist, _ = np.histogram(all_lum, bins=20, range=(0, 1))
    p_low = hist[:5].sum() / hist.sum()
    p_high = hist[15:].sum() / hist.sum()
    bimodal = (p_low > 0.25 and p_high > 0.15)

    avg_rim = float(np.mean(rim_scores)) if rim_scores else 0.0

    if bimodal and avg_rim > 0.005:
        kind = "dramatic_rim"
        intensity = 0.85
        rim = min(1.0, avg_rim * 30)
        shadow = 0.85
    elif mean < 0.35:
        kind = "noir_lowkey"
        intensity = 0.55
        rim = 0.4
        shadow = 0.9
    elif std < 0.18:
        kind = "painterly_flat"
        intensity = 0.6
        rim = 0.2
        shadow = 0.4
    else:
        kind = "soft_diffuse"
        intensity = 0.7
        rim = 0.3
        shadow = 0.5

    return LightingProfile(
        kind=kind,
        direction="top_left",
        intensity=float(intensity),
        rim_strength=float(rim),
        shadow_hardness=float(shadow),
        notes=f"avg_lum={mean:.2f} std={std:.2f} rim_score={avg_rim:.4f}",
    )


def estimate_silhouette(images: list[np.ndarray]) -> SilhouetteProfile:
    """
    Heurística muito conservadora — silhueta é difícil de medir só com imagens.
    Default razoável; o LLM diretor refina depois.
    """
    return SilhouetteProfile(
        weight="balanced",
        detail_level="moderate",
        readability_at_thumbnail=True,
    )


# ============================================================================
# API pública
# ============================================================================

def extract_partial_dna(references_dir: Path) -> dict:
    """
    Lê todas as imagens em references_dir e retorna um dict com a parte
    computacional do DNA (palette + lighting + silhouette).

    O LLM diretor preenche os tokens textuais e LoRAs depois.
    """
    if not references_dir.exists():
        raise FileNotFoundError(f"Pasta de referências não existe: {references_dir}")

    image_paths = sorted([
        p for p in references_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    ])
    if not image_paths:
        raise ValueError(f"Nenhuma imagem encontrada em {references_dir}")

    images = []
    for p in image_paths:
        try:
            images.append(_load_image_rgb(p))
        except Exception as e:
            print(f"AVISO: falha ao carregar {p}: {e}")
    if not images:
        raise RuntimeError("Nenhuma referência pôde ser carregada.")

    palette = extract_palette(images, n_colors=8)
    lighting = estimate_lighting(images)
    silhouette = estimate_silhouette(images)

    return {
        "palette": [c.model_dump() for c in palette],
        "lighting": lighting.model_dump(),
        "silhouette": silhouette.model_dump(),
        "references_used": [str(p.relative_to(references_dir.parent)) for p in image_paths],
        "_reference_count": len(images),
    }


def save_dna(project_dir: Path, dna: StyleDNA) -> Path:
    """Persiste o DNA em projects/<game>/style_dna.json."""
    dna.updated_at = datetime.utcnow()
    out = project_dir / DNA_FILENAME
    out.write_text(dna.model_dump_json(indent=2), encoding="utf-8")
    return out


def load_dna(project_dir: Path) -> Optional[StyleDNA]:
    """Carrega o DNA persistido. Retorna None se não existir."""
    path = project_dir / DNA_FILENAME
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return StyleDNA(**data)


def merge_new_references(
    existing_dna: StyleDNA,
    new_references_dir: Path,
    blend_weight: float = 0.3,
) -> dict:
    """
    Mescla novas referências ao DNA existente.

    Retorna um dict com `proposed_changes` que o LLM diretor revisa antes de aplicar.
    O sistema deliberadamente NÃO aplica automaticamente — mudança de DNA é evento
    deliberado, não automático.
    """
    new_partial = extract_partial_dna(new_references_dir)

    # Blend de paleta
    existing_pal = {c.hex: c.weight for c in existing_dna.palette}
    new_pal = {c["hex"]: c["weight"] for c in new_partial["palette"]}

    merged = {}
    all_keys = set(existing_pal) | set(new_pal)
    for k in all_keys:
        e = existing_pal.get(k, 0.0)
        n = new_pal.get(k, 0.0)
        merged[k] = (1 - blend_weight) * e + blend_weight * n
    # Normaliza e mantém top 8
    total = sum(merged.values()) or 1.0
    sorted_pal = sorted(merged.items(), key=lambda kv: -kv[1])[:8]
    proposed_palette = [
        ColorEntry(hex=h, weight=w / total).model_dump()
        for h, w in sorted_pal
    ]

    return {
        "proposed_palette": proposed_palette,
        "current_palette": [c.model_dump() for c in existing_dna.palette],
        "new_lighting_analysis": new_partial["lighting"],
        "current_lighting": existing_dna.lighting.model_dump(),
        "new_references_count": new_partial["_reference_count"],
        "suggestion": (
            "Revise as mudanças propostas. Se aceitar, chame apply_dna_update() "
            "com os campos que quer adotar."
        ),
    }
