"""
project_memory.py — persistência e estado de um projeto (jogo).

Responsabilidades:
- Criar a estrutura de pastas de um projeto novo (copiando _template/)
- Ler/escrever project.yaml, design/*.json
- Append no generation_log.jsonl
- Responder consultas: "que unidades já existem?", "qual seed gerou esse asset?"

O orquestrador, o Claude Code e os scripts CLI conversam com o projeto sempre
via esta camada — nunca lendo arquivos diretamente. Garante consistência.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .schemas import (
    Building,
    Civilization,
    GenerationLogEntry,
    GenerationPlan,
    GenerationTask,
    ProjectMeta,
    StyleDNA,
    TerrainTile,
    Unit,
)


# ============================================================================
# Caminhos canônicos dentro de um projeto
# ============================================================================

PROJECT_FILENAMES = {
    "meta": "project.yaml",
    "dna": "style_dna.json",
    "civilizations": "design/civilizations.json",
    "buildings": "design/buildings.json",
    "terrain": "design/terrain.json",
    "ui": "design/ui.json",
    "plans": "design/plans/",       # múltiplos planos histórico
    "generation_log": "generation_log.jsonl",
}


def project_path(projects_root: Path, project_name: str) -> Path:
    return projects_root / project_name


# ============================================================================
# Criação de projeto
# ============================================================================

def create_project(
    projects_root: Path,
    name: str,
    *,
    display_name: Optional[str] = None,
    genre: str = "rts",
    platform: str = "android",
    tone: Optional[str] = None,
    description: Optional[str] = None,
    author: Optional[str] = None,
) -> Path:
    """
    Cria a estrutura de um projeto novo a partir do _template/.

    Retorna o path do projeto criado.
    """
    template_dir = projects_root / "_template"
    if not template_dir.exists():
        raise FileNotFoundError(
            f"_template não existe em {template_dir}. Sistema corrompido?"
        )

    target = projects_root / name
    if target.exists():
        raise FileExistsError(f"Projeto já existe: {target}")

    shutil.copytree(template_dir, target)

    meta = ProjectMeta(
        name=name,
        display_name=display_name or name.replace("_", " ").title(),
        genre=genre,
        platform=platform,
        tone=tone,
        description=description,
        author=author,
    )
    save_meta(target, meta)
    return target


# ============================================================================
# Project meta
# ============================================================================

def load_meta(project_dir: Path) -> ProjectMeta:
    path = project_dir / PROJECT_FILENAMES["meta"]
    if not path.exists():
        raise FileNotFoundError(f"{path} não existe — projeto inválido")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ProjectMeta(**data)


def save_meta(project_dir: Path, meta: ProjectMeta) -> Path:
    path = project_dir / PROJECT_FILENAMES["meta"]
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(meta.model_dump_json())  # via JSON pra serializar datetime
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


# ============================================================================
# Design files
# ============================================================================

def load_civilizations(project_dir: Path) -> list[Civilization]:
    path = project_dir / PROJECT_FILENAMES["civilizations"]
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Civilization(**c) for c in data.get("civilizations", [])]


def save_civilizations(project_dir: Path, civs: list[Civilization]) -> Path:
    path = project_dir / PROJECT_FILENAMES["civilizations"]
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"civilizations": [json.loads(c.model_dump_json()) for c in civs]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_buildings(project_dir: Path) -> list[Building]:
    path = project_dir / PROJECT_FILENAMES["buildings"]
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Building(**b) for b in data.get("buildings", [])]


def save_buildings(project_dir: Path, buildings: list[Building]) -> Path:
    path = project_dir / PROJECT_FILENAMES["buildings"]
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"buildings": [json.loads(b.model_dump_json()) for b in buildings]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_terrain(project_dir: Path) -> list[TerrainTile]:
    path = project_dir / PROJECT_FILENAMES["terrain"]
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [TerrainTile(**t) for t in data.get("terrain", [])]


def save_terrain(project_dir: Path, tiles: list[TerrainTile]) -> Path:
    path = project_dir / PROJECT_FILENAMES["terrain"]
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"terrain": [json.loads(t.model_dump_json()) for t in tiles]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ============================================================================
# Planos
# ============================================================================

def save_plan(project_dir: Path, plan: GenerationPlan) -> Path:
    plans_dir = project_dir / PROJECT_FILENAMES["plans"]
    plans_dir.mkdir(parents=True, exist_ok=True)
    path = plans_dir / f"{plan.plan_id}.json"
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_plan(project_dir: Path, plan_id: str) -> GenerationPlan:
    path = project_dir / PROJECT_FILENAMES["plans"] / f"{plan_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return GenerationPlan(**data)


def list_plans(project_dir: Path) -> list[str]:
    plans_dir = project_dir / PROJECT_FILENAMES["plans"]
    if not plans_dir.exists():
        return []
    return sorted([p.stem for p in plans_dir.glob("*.json")])


# ============================================================================
# Generation log (append-only)
# ============================================================================

def log_generation(project_dir: Path, entry: GenerationLogEntry) -> None:
    path = project_dir / PROJECT_FILENAMES["generation_log"]
    path.parent.mkdir(parents=True, exist_ok=True)
    line = entry.model_dump_json()
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def replay_log(project_dir: Path):
    """Generator de todas as entradas do log, ordem cronológica."""
    path = project_dir / PROJECT_FILENAMES["generation_log"]
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            yield GenerationLogEntry(**data)


# ============================================================================
# Consultas convenientes
# ============================================================================

def find_unit(project_dir: Path, unit_id: str) -> Optional[Unit]:
    for civ in load_civilizations(project_dir):
        for unit in civ.units:
            if unit.id == unit_id:
                return unit
    return None


def find_master_seed(project_dir: Path, unit_id: str) -> Optional[int]:
    """Retorna a seed do master sheet aprovado (se houver)."""
    for entry in replay_log(project_dir):
        if entry.asset_kind == "unit_master" and entry.target_ref == unit_id and entry.status == "succeeded":
            return entry.seed
    return None


def assets_summary(project_dir: Path) -> dict:
    """
    Conta o que já foi gerado vs. planejado. Útil pra Claude Code reportar
    progresso ao usuário sem ler todos os arquivos.
    """
    civs = load_civilizations(project_dir)
    buildings = load_buildings(project_dir)
    terrain = load_terrain(project_dir)

    total_units = sum(len(c.units) for c in civs)
    completed_units = sum(
        1 for c in civs for u in c.units
        if u.generation_status in ("completed", "approved")
    )

    return {
        "civilizations": len(civs),
        "units_total": total_units,
        "units_completed": completed_units,
        "buildings_total": len(buildings),
        "buildings_completed": sum(1 for b in buildings if b.generation_status == "completed"),
        "terrain_total": len(terrain),
        "terrain_completed": sum(1 for t in terrain if t.generation_status == "completed"),
    }
