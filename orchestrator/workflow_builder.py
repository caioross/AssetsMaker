"""
workflow_builder.py — carrega templates ComfyUI (formato API) e injeta parâmetros.

Templates ficam em workflows/*.json. Eles foram exportados do ComfyUI com a
opção "Save (API Format)" — diferente do formato "Save" que inclui posições e UI.

Cada template tem placeholders em campos string como ``"@@PROMPT@@"`` e
``"@@SEED@@"``. O builder substitui esses placeholders por valores da GenerationTask.

Isso é mais robusto que tentar localizar nós por ID (que muda quando você edita
o workflow no UI). Você abre o template no ComfyUI, edita à vontade, basta
manter os placeholders nos nós certos.
"""
from __future__ import annotations

import copy
import json
import random
from pathlib import Path
from typing import Any

from .schemas import GenerationTask, LoRABinding, WorkflowKind


# ============================================================================
# Placeholders suportados — documentação viva
# ============================================================================
# Qualquer placeholder não-conhecido é deixado inalterado (o template pode ter
# valores estáticos próprios).
#
# Strings:
#   @@PROMPT@@                — prompt positivo
#   @@NEGATIVE@@              — prompt negativo
#   @@CHECKPOINT@@            — nome do .safetensors do checkpoint
#   @@VAE@@                   — nome do VAE
#   @@IPADAPTER_MODEL@@       — nome do .safetensors do IP-Adapter
#   @@IPADAPTER_REFERENCE@@   — path da imagem de referência
#   @@CONTROLNET_DEPTH@@      — nome do ControlNet de profundidade
#   @@CONTROLNET_CANNY@@      — nome do ControlNet canny
#   @@CONTROLNET_INPUT@@      — path da imagem ControlNet de entrada
#   @@CLIP_VISION@@           — nome do CLIP Vision encoder
#   @@LORA_<N>_NAME@@         — nome do LoRA n (n=0..N-1)
#
# Números (inteiros ou floats — o builder converte o tipo do nó):
#   @@SEED@@
#   @@STEPS@@
#   @@CFG@@
#   @@WIDTH@@
#   @@HEIGHT@@
#   @@LORA_<N>_MODEL_WEIGHT@@
#   @@LORA_<N>_CLIP_WEIGHT@@
#   @@IPADAPTER_WEIGHT@@
#   @@CONTROLNET_STRENGTH@@


# ============================================================================
# Builder
# ============================================================================

class WorkflowBuilder:
    def __init__(self, workflows_dir: Path):
        if not workflows_dir.exists():
            raise FileNotFoundError(f"Workflows dir não existe: {workflows_dir}")
        self.dir = workflows_dir
        self._cache: dict[WorkflowKind, dict] = {}

    def load(self, kind: WorkflowKind) -> dict:
        if kind in self._cache:
            return copy.deepcopy(self._cache[kind])
        path = self.dir / f"{kind.value}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"Template não encontrado: {path}. "
                f"Templates disponíveis: {[p.stem for p in self.dir.glob('*.json')]}"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        self._cache[kind] = data
        return copy.deepcopy(data)

    def build(self, task: GenerationTask, *, checkpoint_name: str, vae_name: str) -> dict:
        """Carrega o template do workflow e injeta os valores da task."""
        wf = self.load(task.workflow)

        # Tabela de substituições
        seed = task.seed if task.seed != 0 else random.randint(1, 2**31 - 2)
        subs: dict[str, Any] = {
            "@@PROMPT@@": task.prompt_positive,
            "@@NEGATIVE@@": task.prompt_negative,
            "@@CHECKPOINT@@": checkpoint_name,
            "@@VAE@@": vae_name,
            "@@SEED@@": seed,
            "@@STEPS@@": task.steps,
            "@@CFG@@": task.cfg_scale,
            "@@WIDTH@@": task.width,
            "@@HEIGHT@@": task.height,
            "@@IPADAPTER_WEIGHT@@": task.ipadapter_weight,
            "@@CONTROLNET_STRENGTH@@": task.controlnet_strength,
        }

        if task.ipadapter_reference:
            subs["@@IPADAPTER_REFERENCE@@"] = task.ipadapter_reference
        if task.controlnet_canny:
            subs["@@CONTROLNET_INPUT@@"] = task.controlnet_canny
        if task.controlnet_lineart:
            subs["@@CONTROLNET_INPUT@@"] = task.controlnet_lineart
        if task.controlnet_depth:
            subs["@@CONTROLNET_INPUT@@"] = task.controlnet_depth

        # LoRAs (até 4 slots no template padrão)
        for i, lora in enumerate(task.loras[:4]):
            subs[f"@@LORA_{i}_NAME@@"] = lora.filename
            subs[f"@@LORA_{i}_MODEL_WEIGHT@@"] = lora.model_weight
            subs[f"@@LORA_{i}_CLIP_WEIGHT@@"] = lora.clip_weight

        # Slots não usados de LoRA recebem um placeholder "bypass" — depende do template
        for i in range(len(task.loras), 4):
            subs.setdefault(f"@@LORA_{i}_NAME@@", "")
            subs.setdefault(f"@@LORA_{i}_MODEL_WEIGHT@@", 0.0)
            subs.setdefault(f"@@LORA_{i}_CLIP_WEIGHT@@", 0.0)

        _substitute_in_tree(wf, subs)
        return wf


# ============================================================================
# Helpers internos
# ============================================================================

def _substitute_in_tree(obj: Any, subs: dict[str, Any]) -> None:
    """Substitui placeholders @@FOO@@ recursivamente no JSON do workflow."""
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            obj[k] = _substitute_value(v, subs)
            if isinstance(obj[k], (dict, list)):
                _substitute_in_tree(obj[k], subs)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            obj[i] = _substitute_value(v, subs)
            if isinstance(obj[i], (dict, list)):
                _substitute_in_tree(obj[i], subs)


def _substitute_value(value: Any, subs: dict[str, Any]) -> Any:
    if not isinstance(value, str):
        return value
    # Caso a string SEJA um placeholder isolado, devolve com o tipo original
    if value in subs:
        return subs[value]
    # Caso placeholder esteja embebido em texto, substitui textualmente
    out = value
    for k, v in subs.items():
        if k in out:
            out = out.replace(k, str(v))
    return out
