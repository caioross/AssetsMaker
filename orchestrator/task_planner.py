"""
task_planner.py — decompõe pedidos de alto nível em listas de tarefas concretas.

Este módulo é deliberadamente esquelético. A inteligência real vem do LLM
diretor (Claude Code ou Ollama) que produz o conteúdo (nomes, descrições,
prompts). Aqui ficam:

1. As funções utilitárias que expandem um plano aprovado em GenerationTasks
   concretas — quantas, com quais paths, quais workflows, em que ordem.
2. Helpers para o LLM montar planos válidos (verificações de schema, slot
   filling).

O LLM "fala" com este módulo via JSON estruturado (GenerationPlan no schema).
"""
from __future__ import annotations

import random
import uuid
from pathlib import Path
from typing import Iterable, Optional

from .schemas import (
    AnimationSpec,
    AnimationType,
    Building,
    Civilization,
    GenerationPlan,
    GenerationTask,
    LoRABinding,
    StyleDNA,
    TerrainTile,
    Unit,
    WorkflowKind,
)


# ============================================================================
# Defaults para cada categoria de asset
# ============================================================================

DEFAULTS = {
    "unit_master": {
        "workflow": WorkflowKind.SD15_CHARACTER_ISO,
        "width": 768,
        "height": 1024,
        "steps": 28,
        "cfg_scale": 7.0,
        "controlnet_strength": 0.55,
        "ipadapter_weight": 0.0,  # sem ref ainda no master
    },
    "unit_animation_frame": {
        "workflow": WorkflowKind.VARIANT_IPADAPTER,
        "width": 768,
        "height": 1024,
        "steps": 22,
        "cfg_scale": 6.5,
        "controlnet_strength": 0.5,
        "ipadapter_weight": 0.85,  # forte aderência ao master
    },
    "building": {
        "workflow": WorkflowKind.SD15_BUILDING_ISO,
        "width": 1024,
        "height": 1024,
        "steps": 30,
        "cfg_scale": 7.5,
        "controlnet_strength": 0.7,
        "ipadapter_weight": 0.0,
    },
    "terrain": {
        "workflow": WorkflowKind.SD15_TERRAIN_TILE,
        "width": 768,
        "height": 768,
        "steps": 22,
        "cfg_scale": 6.5,
        "controlnet_strength": 0.0,
        "ipadapter_weight": 0.0,
    },
    "ui_portrait": {
        "workflow": WorkflowKind.SDXL_HERO_SHOT,
        "width": 832,
        "height": 1216,
        "steps": 8,
        "cfg_scale": 2.0,
        "controlnet_strength": 0.0,
        "ipadapter_weight": 0.0,
    },
}


# ============================================================================
# Expansão de planos aprovados em GenerationTasks
# ============================================================================

def expand_unit_master_task(
    *,
    unit: Unit,
    civilization: Civilization,
    dna: StyleDNA,
    project_name: str,
    prompt_positive: str,
    prompt_negative: str,
    seed: Optional[int] = None,
) -> GenerationTask:
    """Cria a task de geração do master sheet de uma unidade."""
    cfg = DEFAULTS["unit_master"]
    target_path = (
        f"assets/civilizations/{civilization.id}/units/{unit.id}/master_sheet.png"
    )

    return GenerationTask(
        id=str(uuid.uuid4())[:8],
        asset_kind="unit_master",
        workflow=cfg["workflow"],
        target_ref=unit.id,
        target_path=target_path,
        prompt_positive=prompt_positive,
        prompt_negative=prompt_negative,
        seed=seed if seed is not None else random.randint(1, 2**31 - 2),
        width=cfg["width"],
        height=cfg["height"],
        steps=cfg["steps"],
        cfg_scale=cfg["cfg_scale"],
        controlnet_strength=cfg["controlnet_strength"],
        ipadapter_weight=cfg["ipadapter_weight"],
        loras=list(dna.pinned_loras),
    )


def expand_unit_animation_tasks(
    *,
    unit: Unit,
    civilization: Civilization,
    dna: StyleDNA,
    master_sheet_path: str,
    prompt_builder,  # callable(unit, animation, direction_idx, frame_idx) -> (pos, neg)
) -> list[GenerationTask]:
    """
    Gera tasks de animação para uma unidade — 1 task por frame por direção.

    `prompt_builder` é função externa (prompt_engineer.py) que constrói os prompts
    contextualmente para cada frame/direção.
    """
    cfg = DEFAULTS["unit_animation_frame"]
    tasks: list[GenerationTask] = []

    for anim_spec in unit.animations:
        for dir_idx in range(anim_spec.directions):
            for frame_idx in range(anim_spec.frames):
                pos, neg = prompt_builder(unit, anim_spec, dir_idx, frame_idx)
                target_path = (
                    f"assets/civilizations/{civilization.id}/units/{unit.id}/"
                    f"animations/{anim_spec.name.value}/"
                    f"{unit.id}_{anim_spec.name.value}_d{dir_idx:01d}_f{frame_idx:03d}.png"
                )
                tasks.append(GenerationTask(
                    id=str(uuid.uuid4())[:8],
                    asset_kind="unit_animation_frame",
                    workflow=cfg["workflow"],
                    target_ref=unit.id,
                    target_path=target_path,
                    prompt_positive=pos,
                    prompt_negative=neg,
                    seed=random.randint(1, 2**31 - 2),
                    width=cfg["width"],
                    height=cfg["height"],
                    steps=cfg["steps"],
                    cfg_scale=cfg["cfg_scale"],
                    ipadapter_reference=master_sheet_path,
                    ipadapter_weight=cfg["ipadapter_weight"],
                    controlnet_strength=cfg["controlnet_strength"],
                    loras=list(dna.pinned_loras),
                ))
    return tasks


def expand_building_task(
    *,
    building: Building,
    dna: StyleDNA,
    prompt_positive: str,
    prompt_negative: str,
    seed: Optional[int] = None,
) -> GenerationTask:
    cfg = DEFAULTS["building"]
    target_path = (
        f"assets/civilizations/{building.civilization_id}/buildings/"
        f"{building.id}/master.png"
    )
    return GenerationTask(
        id=str(uuid.uuid4())[:8],
        asset_kind="building",
        workflow=cfg["workflow"],
        target_ref=building.id,
        target_path=target_path,
        prompt_positive=prompt_positive,
        prompt_negative=prompt_negative,
        seed=seed if seed is not None else random.randint(1, 2**31 - 2),
        width=cfg["width"],
        height=cfg["height"],
        steps=cfg["steps"],
        cfg_scale=cfg["cfg_scale"],
        controlnet_strength=cfg["controlnet_strength"],
        ipadapter_weight=cfg["ipadapter_weight"],
        loras=list(dna.pinned_loras),
    )


def expand_terrain_task(
    *,
    tile: TerrainTile,
    dna: StyleDNA,
    prompt_positive: str,
    prompt_negative: str,
    seed: Optional[int] = None,
) -> GenerationTask:
    cfg = DEFAULTS["terrain"]
    target_path = f"assets/terrain/tiles/{tile.biome}/{tile.id}_v{tile.variant:02d}.png"
    return GenerationTask(
        id=str(uuid.uuid4())[:8],
        asset_kind="terrain",
        workflow=cfg["workflow"],
        target_ref=tile.id,
        target_path=target_path,
        prompt_positive=prompt_positive,
        prompt_negative=prompt_negative,
        seed=seed if seed is not None else random.randint(1, 2**31 - 2),
        width=cfg["width"],
        height=cfg["height"],
        steps=cfg["steps"],
        cfg_scale=cfg["cfg_scale"],
        controlnet_strength=cfg["controlnet_strength"],
        ipadapter_weight=cfg["ipadapter_weight"],
        loras=list(dna.pinned_loras),
    )


# ============================================================================
# Validação de planos
# ============================================================================

def validate_plan(plan: GenerationPlan, dna: StyleDNA) -> list[str]:
    """
    Retorna lista de problemas encontrados no plano. Lista vazia = OK.

    Verificações:
    - IDs únicos
    - Civ IDs referenciados existem
    - Pesos de LoRA dentro de limites razoáveis (-1.5 a 1.5)
    - Prompts não-vazios
    """
    issues: list[str] = []

    civ_ids = {c.id for c in plan.civilizations}
    for c in plan.civilizations:
        for u in c.units:
            if u.civilization_id != c.id:
                issues.append(f"Unit {u.id}: civ_id '{u.civilization_id}' != civ '{c.id}'")

    for b in plan.buildings:
        if b.civilization_id not in civ_ids and b.civilization_id != "neutral":
            issues.append(f"Building {b.id}: civilization_id '{b.civilization_id}' desconhecida")

    seen_ids = set()
    for task in plan.tasks:
        if task.id in seen_ids:
            issues.append(f"Task ID duplicada: {task.id}")
        seen_ids.add(task.id)
        if not task.prompt_positive.strip():
            issues.append(f"Task {task.id}: prompt_positive vazio")
        for lora in task.loras:
            if abs(lora.model_weight) > 1.5:
                issues.append(f"Task {task.id}: LoRA '{lora.filename}' com peso {lora.model_weight} fora do recomendado [-1.5, 1.5]")

    return issues


def estimate_runtime_minutes(tasks: Iterable[GenerationTask]) -> float:
    """Estimativa grosseira em RTX 4050 6GB com SD 1.5."""
    minutes = 0.0
    for t in tasks:
        if t.workflow == WorkflowKind.SDXL_HERO_SHOT:
            minutes += 25 / 60.0
        elif t.workflow in (WorkflowKind.SD15_CHARACTER_ISO, WorkflowKind.VARIANT_IPADAPTER):
            minutes += 12 / 60.0
        elif t.workflow == WorkflowKind.SD15_BUILDING_ISO:
            minutes += 15 / 60.0
        elif t.workflow == WorkflowKind.SD15_TERRAIN_TILE:
            minutes += 8 / 60.0
        else:
            minutes += 12 / 60.0
    return minutes
