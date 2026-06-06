"""
prompt_engineer.py — constrói prompts a partir do Style DNA + contexto da task.

A função do módulo é fazer o "encadeamento" do prompt: começa pelo DNA do
projeto (que entra em TUDO), adiciona tokens de câmera/perspectiva isométrica,
e por fim a descrição específica do asset.

Princípios:
- Tokens importantes vêm cedo (modelos SD dão mais peso para o início)
- Negative prompt é igual de importante — bloqueia artefatos comuns
- Loras com trigger words bem documentados melhoram aderência
"""
from __future__ import annotations

from typing import Optional

from .schemas import (
    AnimationSpec,
    AnimationType,
    Building,
    Civilization,
    StyleDNA,
    TerrainTile,
    Unit,
)


# ============================================================================
# Tokens canônicos por categoria
# ============================================================================

ISOMETRIC_CAMERA_TOKENS = (
    "isometric perspective, dimetric projection, "
    "camera tilted 30 degrees down, viewed from above and side, "
    "2:1 isometric ratio, top-down 3/4 view"
)

CHARACTER_QUALITY_TOKENS = (
    "highly detailed, sharp focus, full body shot, clean background, "
    "centered composition, neutral pose, game asset, sprite"
)

BUILDING_QUALITY_TOKENS = (
    "highly detailed architecture, complete structure, clean white background, "
    "isometric building, game-ready asset, sharp materials, no humans"
)

TERRAIN_QUALITY_TOKENS = (
    "seamless tileable texture, top-down isometric tile, "
    "consistent lighting, no shadows on edges, game ground tile"
)


# Direções isométricas em texto (8 direções)
DIRECTION_DESCRIPTIONS = {
    0: "facing south, viewer sees front of unit",
    1: "facing south-west, three-quarter front-left",
    2: "facing west, side profile from left",
    3: "facing north-west, three-quarter back-left",
    4: "facing north, back of unit visible",
    5: "facing north-east, three-quarter back-right",
    6: "facing east, side profile from right",
    7: "facing south-east, three-quarter front-right",
}


# Descrições de fase de animação
ANIMATION_PHASE_TEXT = {
    AnimationType.IDLE: "standing pose, relaxed stance, ready for action",
    AnimationType.WALK: "walking forward, mid-stride, weight on one leg",
    AnimationType.RUN: "running forward, dynamic action, motion blur on legs",
    AnimationType.ATTACK: "attacking pose, mid-swing, weapon raised, aggressive expression",
    AnimationType.DEATH: "falling down, dying pose, dramatic, defeated",
    AnimationType.GATHER: "gathering resources, bent forward, working pose",
    AnimationType.BUILD: "building action, hammering or constructing, focused",
    AnimationType.CAST: "casting spell, hands raised, magical energy gathering",
}


# ============================================================================
# Construtores de prompt
# ============================================================================

def _dna_prefix(dna: StyleDNA) -> str:
    """Tokens do DNA que precedem qualquer asset deste projeto."""
    return ", ".join(dna.style_tokens)


def _dna_negative(dna: StyleDNA, extra: Optional[list[str]] = None) -> str:
    tokens = list(dna.negative_tokens)
    if extra:
        tokens.extend(extra)
    return ", ".join(tokens)


def build_unit_master_prompt(
    *,
    unit: Unit,
    civilization: Civilization,
    dna: StyleDNA,
) -> tuple[str, str]:
    """Constrói prompt positivo/negativo para o master sheet de uma unidade."""
    parts = [
        _dna_prefix(dna),
        ISOMETRIC_CAMERA_TOKENS,
        f"a {civilization.name} {unit.role.value}",
        unit.description.strip(),
        f"primary color {unit.primary_color}",
    ]
    if unit.accessories:
        parts.append("wearing/carrying " + ", ".join(unit.accessories))
    if unit.distinguishing_features:
        parts.append(", ".join(unit.distinguishing_features))
    parts.append(CHARACTER_QUALITY_TOKENS)
    parts.append("standing idle, T-pose neutral, reference sheet pose")

    # LoRA trigger words automaticamente
    for lora in dna.pinned_loras:
        if lora.trigger_words:
            parts.extend(lora.trigger_words)

    pos = ", ".join(parts)
    neg = _dna_negative(dna, extra=["multiple characters", "crowd", "background scene"])
    return pos, neg


def build_unit_animation_prompt(
    *,
    unit: Unit,
    animation: AnimationSpec,
    direction_idx: int,
    frame_idx: int,
    dna: StyleDNA,
) -> tuple[str, str]:
    """Prompt para um frame específico de animação de unidade."""
    phase = ANIMATION_PHASE_TEXT.get(animation.name, "")
    direction = DIRECTION_DESCRIPTIONS.get(direction_idx, "")

    # Fração do frame na animação — usado pra modular o prompt em frames críticos
    frame_progress = frame_idx / max(1, animation.frames - 1)

    parts = [
        _dna_prefix(dna),
        ISOMETRIC_CAMERA_TOKENS,
        f"a {unit.role.value}",
        unit.description.strip(),
        phase,
        direction,
    ]

    # Frame-level hint: para attack, intensifica entre frame 0.3-0.7
    if animation.name == AnimationType.ATTACK:
        if 0.3 <= frame_progress <= 0.7:
            parts.append("peak action, weapon connecting, dynamic")
        elif frame_progress < 0.3:
            parts.append("wind-up phase, charging attack")
        else:
            parts.append("follow-through, completing swing")

    parts.append(CHARACTER_QUALITY_TOKENS)

    for lora in dna.pinned_loras:
        if lora.trigger_words:
            parts.extend(lora.trigger_words)

    pos = ", ".join(parts)
    neg = _dna_negative(dna, extra=["multiple characters", "different character"])
    return pos, neg


def build_building_prompt(
    *,
    building: Building,
    dna: StyleDNA,
) -> tuple[str, str]:
    parts = [
        _dna_prefix(dna),
        ISOMETRIC_CAMERA_TOKENS,
        f"{building.category.value} building",
        building.description.strip(),
        BUILDING_QUALITY_TOKENS,
        f"footprint {building.tile_footprint[0]}x{building.tile_footprint[1]} tiles",
    ]
    for lora in dna.pinned_loras:
        if lora.trigger_words:
            parts.extend(lora.trigger_words)
    pos = ", ".join(parts)
    neg = _dna_negative(dna, extra=["people", "humans", "characters", "units"])
    return pos, neg


def build_terrain_prompt(
    *,
    tile: TerrainTile,
    dna: StyleDNA,
) -> tuple[str, str]:
    parts = [
        _dna_prefix(dna),
        f"{tile.biome} terrain ground tile",
        f"variant {tile.variant}",
        TERRAIN_QUALITY_TOKENS,
    ]
    if tile.decoration_props:
        parts.append("with " + ", ".join(tile.decoration_props))
    for lora in dna.pinned_loras:
        if lora.trigger_words:
            parts.extend(lora.trigger_words)
    pos = ", ".join(parts)
    neg = _dna_negative(dna, extra=["people", "buildings", "scene", "depth"])
    return pos, neg


# ============================================================================
# Helper para o task_planner: monta callable que ele pode chamar
# ============================================================================

def make_animation_prompt_builder(dna: StyleDNA):
    """
    Retorna função callable(unit, animation, direction_idx, frame_idx) -> (pos, neg)
    pré-bindada ao DNA. Usado pelo task_planner.expand_unit_animation_tasks.
    """
    def _builder(unit, animation, direction_idx, frame_idx):
        return build_unit_animation_prompt(
            unit=unit,
            animation=animation,
            direction_idx=direction_idx,
            frame_idx=frame_idx,
            dna=dna,
        )
    return _builder
