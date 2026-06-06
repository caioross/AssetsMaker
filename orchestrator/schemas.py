"""
schemas.py — todos os modelos Pydantic que estruturam o pipeline.

Princípio: tudo que cruza fronteiras (LLM → orquestrador, orquestrador → ComfyUI,
ComfyUI → asset_processor) passa por um destes schemas. Quebra cedo, quebra alto.

Esses schemas também servem como referência viva: o Claude Code lê-os para saber
exatamente que JSON ele deve produzir quando atuar como Diretor de Arte.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Style DNA — a identidade visual congelada de um jogo
# ============================================================================

class ColorEntry(BaseModel):
    """Uma cor da paleta, com peso de dominância."""
    hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    weight: float = Field(ge=0.0, le=1.0, description="Peso na paleta (0-1).")
    label: Optional[str] = Field(None, description="Rótulo semântico (ex: 'metal frio', 'sangue').")


class LightingProfile(BaseModel):
    """Como a luz funciona no estilo do jogo."""
    kind: Literal[
        "dramatic_rim", "soft_diffuse", "high_contrast", "painterly_flat",
        "miniature_diorama", "noir_lowkey", "stylized_toon"
    ]
    direction: Literal["top", "top_left", "top_right", "side", "back", "ambient"] = "top_left"
    intensity: float = Field(ge=0.0, le=1.0, default=0.7)
    rim_strength: float = Field(ge=0.0, le=1.0, default=0.5)
    shadow_hardness: float = Field(ge=0.0, le=1.0, default=0.6)
    notes: Optional[str] = None


class SilhouetteProfile(BaseModel):
    """Proporção e peso visual das unidades."""
    weight: Literal["slim", "balanced", "chunky", "exaggerated"]
    head_to_body: float = Field(default=0.18, description="Proporção cabeça/corpo (~0.18 humano realista).")
    detail_level: Literal["minimal", "moderate", "high", "ornate"] = "moderate"
    readability_at_thumbnail: bool = Field(
        True,
        description="True se a silhueta precisa ser lida em ícone pequeno (mobile).",
    )


class StyleDNA(BaseModel):
    """
    DNA visual congelado de um projeto. Tudo que é gerado naquele jogo aderem a este DNA.

    Persistido em projects/<game>/style_dna.json. Versionado: cada update incrementa
    `version` e mantém histórico em `revisions`.
    """
    project_name: str
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Tokens textuais — o coração do prompt engineering
    style_tokens: list[str] = Field(
        ...,
        description=(
            "Tokens-chave que entram em todo prompt do projeto. Ex: "
            "['dark fantasy', 'gritty', 'cinematic lighting', 'high detail armor']"
        ),
        min_length=3,
    )
    negative_tokens: list[str] = Field(
        default_factory=lambda: [
            "blurry", "low quality", "watermark", "text", "signature",
            "extra limbs", "deformed", "amateur"
        ]
    )

    # Análise visual extraída das referências
    palette: list[ColorEntry] = Field(..., min_length=3, max_length=12)
    lighting: LightingProfile
    silhouette: SilhouetteProfile

    # Materiais predominantes
    material_tags: list[str] = Field(
        default_factory=list,
        description="Tags de materiais que predominam (ex: 'leather', 'rusted iron', 'glowing runes').",
    )

    # Câmera isométrica do projeto
    camera_angle_deg: float = Field(default=30.0, description="Ângulo de declinação isométrico (graus).")
    camera_rotation_deg: float = Field(default=45.0, description="Rotação horizontal (graus).")
    iso_ratio: tuple[int, int] = Field(default=(2, 1), description="Proporção de projeção (2:1 dimétrico).")

    # LoRAs que devem entrar em todas as gerações deste projeto
    pinned_loras: list["LoRABinding"] = Field(default_factory=list)

    # Modelo preferencial — pode ser sobrescrito por categoria
    preferred_model: Literal["sd15", "sdxl_lightning"] = "sd15"

    # Histórico
    revisions: list["StyleDNARevision"] = Field(default_factory=list)
    references_used: list[str] = Field(
        default_factory=list,
        description="Paths relativos das imagens de referência que geraram esse DNA.",
    )

    @field_validator("style_tokens")
    @classmethod
    def _validate_tokens(cls, v: list[str]) -> list[str]:
        v = [t.strip() for t in v if t.strip()]
        if len(v) < 3:
            raise ValueError("style_tokens precisa de pelo menos 3 entradas válidas.")
        return v


class StyleDNARevision(BaseModel):
    """Registro de cada mudança no DNA."""
    version: int
    changed_at: datetime
    reason: str
    added_tokens: list[str] = []
    removed_tokens: list[str] = []
    palette_drift: float = Field(default=0.0, description="Distância LAB média entre paletas antes/depois.")


class LoRABinding(BaseModel):
    """Um LoRA aplicado com peso."""
    filename: str = Field(..., description="Nome do arquivo em ComfyUI/models/loras/")
    model_weight: float = Field(default=0.7, ge=-2.0, le=2.0)
    clip_weight: float = Field(default=0.7, ge=-2.0, le=2.0)
    trigger_words: list[str] = Field(default_factory=list)


# ============================================================================
# Projeto — o jogo em si
# ============================================================================

class ProjectMeta(BaseModel):
    """Metadados do jogo. Persistido em projects/<game>/project.yaml."""
    name: str = Field(..., description="Identificador único (slug). Ex: 'fjord_wars'.")
    display_name: str = Field(..., description="Nome legível. Ex: 'Fjord Wars'.")
    genre: str = Field(default="rts")
    platform: Literal["android", "ios", "pc", "web", "multi"] = "android"
    target_resolution: tuple[int, int] = (1080, 1920)
    tone: Optional[str] = Field(None, description="Ex: 'dark fantasy', 'cyberpunk noir', 'cozy'.")
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    author: Optional[str] = None
    dna_version: int = 1


# ============================================================================
# Hierarquia de design: civilizações, unidades, prédios, terreno
# ============================================================================

class AnimationType(str, Enum):
    IDLE = "idle"
    WALK = "walk"
    RUN = "run"
    ATTACK = "attack"
    DEATH = "death"
    GATHER = "gather"
    BUILD = "build"
    CAST = "cast"


class AnimationSpec(BaseModel):
    name: AnimationType
    frames: int = Field(default=8, ge=1, le=64)
    directions: int = Field(default=8, description="Tipicamente 8 (isométrico).", ge=1, le=16)
    loop: bool = True


class UnitRole(str, Enum):
    WORKER = "worker"
    SCOUT = "scout"
    MELEE = "melee"
    RANGED = "ranged"
    SIEGE = "siege"
    HEALER = "healer"
    CASTER = "caster"
    HERO = "hero"
    BEAST = "beast"
    SIEGE_VEHICLE = "siege_vehicle"


class Unit(BaseModel):
    id: str = Field(..., description="Slug único: ex 'vikings_berserker'.")
    civilization_id: str
    name: str
    role: UnitRole
    description: str = Field(..., description="Lore + traços visuais únicos.")

    # Visuais
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    accessories: list[str] = Field(default_factory=list, description="Ex: ['greataxe', 'horned helmet'].")
    distinguishing_features: list[str] = Field(default_factory=list)

    # Animações alvo
    animations: list[AnimationSpec] = Field(
        default_factory=lambda: [
            AnimationSpec(name=AnimationType.IDLE, frames=8),
            AnimationSpec(name=AnimationType.WALK, frames=12),
            AnimationSpec(name=AnimationType.ATTACK, frames=10),
            AnimationSpec(name=AnimationType.DEATH, frames=8),
        ]
    )

    # Estado de geração
    master_sheet_path: Optional[str] = None
    master_approved: bool = False
    master_seed: Optional[int] = None
    generation_status: Literal["pending", "in_progress", "completed", "approved", "rejected"] = "pending"


class Civilization(BaseModel):
    id: str
    name: str
    lore: str
    visual_traits: str = Field(..., description="Resumo curto: 'pele pálida, peles de animal, runas brilhantes...'")
    secondary_palette: list[str] = Field(
        default_factory=list,
        description="Cores que distinguem essa civ da paleta global.",
    )
    units: list[Unit] = Field(default_factory=list)


class BuildingCategory(str, Enum):
    TOWNHALL = "townhall"
    HOUSING = "housing"
    BARRACKS = "barracks"
    RESOURCE = "resource"
    DEFENSE = "defense"
    WONDER = "wonder"
    DECORATION = "decoration"


class Building(BaseModel):
    id: str
    civilization_id: str
    name: str
    category: BuildingCategory
    description: str
    tile_footprint: tuple[int, int] = (2, 2)
    has_destroyed_state: bool = True
    construction_stages: int = Field(default=3, ge=1, le=5)
    generation_status: Literal["pending", "in_progress", "completed"] = "pending"
    master_sheet_path: Optional[str] = None


class TerrainTile(BaseModel):
    id: str
    biome: str = Field(..., description="Ex: 'grass', 'snow', 'rock', 'tundra', 'corrupted'.")
    variant: int = Field(default=1, ge=1, le=16)
    blendable: bool = True
    decoration_props: list[str] = Field(default_factory=list)
    generation_status: Literal["pending", "in_progress", "completed"] = "pending"


# ============================================================================
# Tarefas de geração — o que vai pro ComfyUI
# ============================================================================

class WorkflowKind(str, Enum):
    SD15_CHARACTER_ISO = "sd15_character_iso"
    SD15_BUILDING_ISO = "sd15_building_iso"
    SD15_TERRAIN_TILE = "sd15_terrain_tile"
    SDXL_HERO_SHOT = "sdxl_hero_shot"
    SDXL_UI_PORTRAIT = "sdxl_ui_portrait"
    VARIANT_IPADAPTER = "variant_ipadapter"
    STYLE_DNA_PROBE = "style_dna_probe"


class GenerationTask(BaseModel):
    """
    Uma unidade atômica de trabalho para o ComfyUI.

    Tudo que vai pro ComfyUI passa por aqui. Isso garante que o histórico em
    generation_log.jsonl seja completo o suficiente para regenerar exatamente
    o mesmo PNG mais tarde.
    """
    id: str = Field(..., description="UUID curto.")
    asset_kind: Literal["unit_master", "unit_animation_frame", "building", "terrain", "ui_portrait", "prop"]
    workflow: WorkflowKind

    # O que estamos gerando
    target_ref: str = Field(..., description="ID do unit/building/tile sendo gerado.")
    target_path: str = Field(..., description="Path relativo onde o PNG final será salvo.")

    # Inputs
    prompt_positive: str
    prompt_negative: str
    seed: int = Field(..., ge=0, le=2**31 - 1)
    width: int = 1024
    height: int = 1024
    steps: int = 25
    cfg_scale: float = 7.0
    loras: list[LoRABinding] = Field(default_factory=list)

    # Inputs visuais (paths)
    ipadapter_reference: Optional[str] = None
    controlnet_canny: Optional[str] = None
    controlnet_lineart: Optional[str] = None
    controlnet_depth: Optional[str] = None

    # Pesos de controle
    ipadapter_weight: float = Field(default=0.7, ge=0.0, le=2.0)
    controlnet_strength: float = Field(default=0.7, ge=0.0, le=2.0)

    # Pós-processamento
    remove_background: bool = True
    upscale: Optional[int] = Field(None, description="Fator de upscale (None, 2, 4).")
    upscaler: Optional[str] = "RealESRGAN_x4plus"

    # Resultado
    status: Literal["pending", "running", "succeeded", "failed", "rejected"] = "pending"
    result_path: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    runtime_seconds: Optional[float] = None


# ============================================================================
# Plano de bootstrap — o que o LLM diretor produz
# ============================================================================

class GenerationPlan(BaseModel):
    """
    Saída do task_planner: tudo que precisa ser gerado para um pedido.

    O LLM diretor produz isso e o orquestrador executa.
    """
    project_name: str
    plan_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reason: str = Field(..., description="Por que esse plano existe ('bootstrap', 'add_civ', 'expansion', etc.).")

    civilizations: list[Civilization] = Field(default_factory=list)
    buildings: list[Building] = Field(default_factory=list)
    terrain: list[TerrainTile] = Field(default_factory=list)
    tasks: list[GenerationTask] = Field(default_factory=list)

    summary_text: str = Field(..., description="Resumo humano-legível do plano (mostrado ao usuário antes de aprovar).")
    estimated_runtime_minutes: float = Field(..., ge=0.0)
    requires_approval: bool = True


# ============================================================================
# Log persistente
# ============================================================================

class GenerationLogEntry(BaseModel):
    """Linha do generation_log.jsonl — uma por task executada."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    task_id: str
    workflow: WorkflowKind
    asset_kind: str
    target_ref: str
    target_path: str
    seed: int
    prompt_positive: str
    prompt_negative: str
    loras: list[LoRABinding] = []
    runtime_seconds: float
    status: Literal["succeeded", "failed"]
    error: Optional[str] = None


# ============================================================================
# Resolve forward refs
# ============================================================================
StyleDNA.model_rebuild()
