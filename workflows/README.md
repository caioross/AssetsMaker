# Workflows ComfyUI

Templates em **formato API** (ComfyUI: menu hamburger → Workflow → Export (API)). Cada arquivo aqui é um grafo que o `orchestrator.workflow_builder.WorkflowBuilder` carrega e preenche com valores da `GenerationTask` via placeholders `@@PLACEHOLDER@@`.

## Templates atuais

| Arquivo | Para que serve |
|---------|----------------|
| `sd15_character_iso.json` | Unidades isométricas. SD 1.5 + ControlNet Depth + IP-Adapter + 2 LoRAs. Volume normal. |
| `sd15_building_iso.json` | Prédios isométricos. SD 1.5 + ControlNet Lineart (sem IP-Adapter, prédios não precisam). |
| `sd15_terrain_tile.json` | Tiles de terreno. SD 1.5 puro, square. |
| `sdxl_hero_shot.json` | Hero portraits, UI premium. SDXL Lightning 8-step. |
| `variant_ipadapter.json` | Animações/variantes. IP-Adapter peso alto para coerência com master sheet. |
| `style_dna_probe.json` | Smoke test do estilo. SD 1.5 + LoRAs, sem controle visual extra. |

## Placeholders aceitos

Veja `orchestrator/workflow_builder.py` no topo do arquivo — lista completa documentada. Resumo:

**Strings:**
- `@@PROMPT@@`, `@@NEGATIVE@@`
- `@@CHECKPOINT@@`, `@@VAE@@`
- `@@LORA_0_NAME@@`, `@@LORA_1_NAME@@`, ..., `@@LORA_3_NAME@@`
- `@@IPADAPTER_REFERENCE@@`, `@@CONTROLNET_INPUT@@`

**Numéricos:**
- `@@SEED@@`, `@@STEPS@@`, `@@CFG@@`, `@@WIDTH@@`, `@@HEIGHT@@`
- `@@LORA_N_MODEL_WEIGHT@@`, `@@LORA_N_CLIP_WEIGHT@@`
- `@@IPADAPTER_WEIGHT@@`, `@@CONTROLNET_STRENGTH@@`

## Como criar um template novo

1. Abra o ComfyUI em http://localhost:8188 (rode `start_pipeline.ps1`)
2. Construa o grafo no UI até estar funcionando com valores reais
3. Menu → **Workflow → Save (API Format)** — salva como JSON
4. Abra o JSON salvo aqui em `workflows/`
5. Substitua valores hardcoded pelos placeholders correspondentes (`@@PROMPT@@`, etc.)
6. Adicione o novo `WorkflowKind` em `orchestrator/schemas.py`
7. Use a `WorkflowKind` nova nas `GenerationTask` que devem usar esse template

## Notas sobre VRAM (RTX 4050 6GB)

- Os templates SD 1.5 cabem confortavelmente em 6GB com `--medvram`
- `sdxl_hero_shot.json` exige `--lowvram` ou `--medvram-sdxl`. Use para um sprite por vez, não para batch.
- Se OOM persistir: reduza `@@WIDTH@@`/`@@HEIGHT@@` para 768x768 (SD 1.5) ou 832x1216 (SDXL)
- O `comfy_client.execute_with_oom_fallback()` já degrada automaticamente em OOM
