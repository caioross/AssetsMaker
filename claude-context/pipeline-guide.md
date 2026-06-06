# Pipeline Guide — Receitas Operacionais

Receitas concretas para o Claude Code operar o sistema. Cada receita é um fluxo que você executará várias vezes.

---

## Receita 1 — Bootstrap de um projeto novo

**Disparada por:** "vamos criar um jogo novo chamado X", "começar projeto Y", primeiro contato com um projeto.

```python
from pathlib import Path
from orchestrator import project_memory

ROOT = Path(r"E:\Projetos\SISTEMA AssetsMaker")
PROJECTS = ROOT / "projects"

# 1. Cria estrutura
project_dir = project_memory.create_project(
    PROJECTS,
    name="fjord_wars",                # slug
    display_name="Fjord Wars",
    genre="rts",
    platform="android",
    tone="dark fantasy viking",
    description="RTS móvel ambientado em fjords nórdicos, mitologia",
    author="Caio",
)
print(f"Criado em {project_dir}")
```

**Depois disso:**

1. Diga ao Caio onde foi criado
2. Peça pra ele jogar 5-15 imagens em `projects/fjord_wars/references/`
3. Quando ele confirmar, parta para a Receita 2

---

## Receita 2 — Extrair Style DNA de um projeto

**Disparada por:** "extrai o DNA", "analisa as referências", "já joguei as referências".

```python
from orchestrator import style_dna
from orchestrator.schemas import StyleDNA, LoRABinding, ColorEntry, LightingProfile, SilhouetteProfile

# 1. Análise computacional
refs_dir = project_dir / "references"
partial = style_dna.extract_partial_dna(refs_dir)

# 2. Você (Claude Code) lê as imagens via Read e complementa
# (Read mostra PNG/JPG visualmente — use isso para entender o estilo)
```

Agora você lê o `prompt-library/style_analyzer.md` e produz o DNA completo. Princípios:

- `style_tokens`: 5-8 tokens em inglês que pegam o estilo
- `negative_tokens`: além dos defaults, bloqueie o que NÃO deve aparecer
- `material_tags`: materiais predominantes nas referências
- `pinned_loras`: 1-2 LoRAs do `ComfyUI/models/loras/` que combinam
- `preferred_model`: `sd15` para volume, `sdxl_lightning` para premium

Mostre **resumo legível** ao Caio:

```
Style DNA proposto para fjord_wars:

Estilo central: dark fantasy + viking + painterly
Lighting: rim light dramático, sombras duras (~ Diablo/PoE)
Paleta: 8 cores dominantes (mostre os hex e o label)
LoRAs: dark_fantasy_sd15 (0.7) + iso_asset_sd15 (0.5)
Modelo: SD 1.5

Congelar como v1? (sim/ajustar/refazer)
```

Só depois de "sim":

```python
dna_obj = StyleDNA(
    project_name="fjord_wars",
    version=1,
    style_tokens=[...],
    negative_tokens=[...],
    palette=[ColorEntry(**c) for c in partial["palette"]],
    lighting=LightingProfile(**partial["lighting"]),
    silhouette=SilhouetteProfile(**partial["silhouette"]),
    material_tags=[...],
    pinned_loras=[LoRABinding(filename="...", model_weight=0.7, ...)],
    references_used=partial["references_used"],
)
style_dna.save_dna(project_dir, dna_obj)
```

---

## Receita 3 — Smoke test do DNA antes de queimar GPU

**Disparada por:** após congelar DNA, antes de bootstrap completo.

Antes de gerar 400 PNGs, gere **1 imagem genérica** com o DNA para validar que o estilo aparece. Use o workflow `style_dna_probe`.

```python
from orchestrator.schemas import GenerationTask, WorkflowKind
from orchestrator.workflow_builder import WorkflowBuilder
from orchestrator.comfy_client import ComfyClient
from orchestrator.asset_processor import finalize_asset

client = ComfyClient(); client.wait_until_alive()
wb = WorkflowBuilder(ROOT / "workflows")

# Prompt manual de teste
prompt_pos = ", ".join(dna_obj.style_tokens) + ", a generic warrior, full body, isometric, clean background"
prompt_neg = ", ".join(dna_obj.negative_tokens)

task = GenerationTask(
    id="dna_probe_001",
    asset_kind="ui_portrait",
    workflow=WorkflowKind.STYLE_DNA_PROBE,
    target_ref="probe",
    target_path="test_outputs/dna_probe.png",
    prompt_positive=prompt_pos,
    prompt_negative=prompt_neg,
    seed=42,
    width=768, height=768, steps=25,
    loras=list(dna_obj.pinned_loras),
)

wf = wb.build(task, checkpoint_name="sd15_dreamshaper8.safetensors",
              vae_name="vae-ft-mse-840000-ema-pruned.safetensors")
result = client.execute(wf)
saved = finalize_asset(result.images[0], project_dir / task.target_path,
                       FinalizeOptions(remove_bg=False))
```

Apresente o PNG ao Caio. "O estilo bate com o que você quer? Se sim, prossigo para o catálogo completo."

---

## Receita 4 — Planejar civilizações + unidades + prédios

**Disparada por:** "monta o catálogo", "planeja as civilizações", "bootstrap do conteúdo".

Para cada civilização (leia `prompt-library/unit_planner.md` e `building_planner.md`):

1. Defina **6 unidades** cobrindo: worker, scout, melee, ranged, siege/caster, hero
2. Defina **8 prédios** cobrindo: townhall, housing, resource, barracks, defense, decoration
3. Para cada um, escreva descrição rica com 2+ ganchos visuais concretos

Use as estruturas do `schemas.py`:

```python
from orchestrator.schemas import Civilization, Unit, UnitRole, AnimationSpec, AnimationType, Building, BuildingCategory

vikings = Civilization(
    id="vikings",
    name="Vikings",
    lore="Raiders from the cold north, drawn south by the call of plunder and Odin's whispers.",
    visual_traits="pale skin, woven beards, fur cloaks, weathered iron, rune tattoos",
    secondary_palette=["#5C4023", "#2A1F18"],
    units=[
        Unit(
            id="vikings_berserker",
            civilization_id="vikings",
            name="Berserker",
            role=UnitRole.MELEE,
            description="Massive bare-chested warrior in trance, wild matted hair, woven beard with bone beads. ...",
            primary_color="#5C4023",
            accessories=["two-handed bearded axe", "wolf pelt cloak"],
            distinguishing_features=["glowing rune tattoos", "crazed eyes"],
            animations=[
                AnimationSpec(name=AnimationType.IDLE, frames=8),
                AnimationSpec(name=AnimationType.WALK, frames=12),
                AnimationSpec(name=AnimationType.ATTACK, frames=10),
                AnimationSpec(name=AnimationType.DEATH, frames=8),
            ],
        ),
        # ... outras 5 unidades
    ],
)
```

**Mostre tabela ao Caio antes de gravar:**

```
Vikings (vikings):
  Unidades: 6 (thrall, scout, huscarl, berserker, archer, jarl)
  Prédios: 8 (longhouse, sod_house, farm, lumber, barracks, watchtower, runestone, hearth)

Estimativa de geração:
  - 6 masters de unidades   →   ~1m 12s
  - 384 frames de animação  →  ~76m
  - 8 prédios               →   ~2m 00s
  TOTAL                       ~80m em GPU

Confirma gravar civilizations.json? (sim/ajustar)
```

Depois de OK:

```python
project_memory.save_civilizations(project_dir, [vikings, saxons])
project_memory.save_buildings(project_dir, todos_os_buildings)
```

---

## Receita 5 — Gerar master sheets de unidades

**Disparada por:** "gera os masters da civ X", "começa pela geração das unidades".

```python
from orchestrator import prompt_engineer
from orchestrator.comfy_client import ComfyClient, execute_with_oom_fallback
from orchestrator.workflow_builder import WorkflowBuilder
from orchestrator.asset_processor import finalize_asset, FinalizeOptions
from orchestrator.schemas import GenerationLogEntry
import time

client = ComfyClient(); client.wait_until_alive()
wb = WorkflowBuilder(ROOT / "workflows")

civs = project_memory.load_civilizations(project_dir)
viking = next(c for c in civs if c.id == "vikings")

for unit in viking.units:
    if unit.master_approved:
        continue  # pula já aprovados

    pos, neg = prompt_engineer.build_unit_master_prompt(unit=unit, civilization=viking, dna=dna_obj)
    task = task_planner.expand_unit_master_task(
        unit=unit,
        civilization=viking,
        dna=dna_obj,
        project_name=meta.name,
        prompt_positive=pos,
        prompt_negative=neg,
    )

    wf = wb.build(task,
                  checkpoint_name="sd15_dreamshaper8.safetensors",
                  vae_name="vae-ft-mse-840000-ema-pruned.safetensors")

    print(f"Gerando master: {unit.id}")
    start = time.time()
    try:
        result = client.execute(wf)
    except Exception as e:
        print(f"  FALHA: {e}")
        continue

    out_path = project_dir / task.target_path
    finalize_asset(result.images[0], out_path, FinalizeOptions(remove_bg=True))

    project_memory.log_generation(project_dir, GenerationLogEntry(
        task_id=task.id,
        workflow=task.workflow,
        asset_kind=task.asset_kind,
        target_ref=task.target_ref,
        target_path=task.target_path,
        seed=task.seed,
        prompt_positive=task.prompt_positive,
        prompt_negative=task.prompt_negative,
        loras=task.loras,
        runtime_seconds=time.time() - start,
        status="succeeded",
    ))

    # Atualiza unit no JSON com status + path
    unit.master_sheet_path = task.target_path
    unit.master_seed = task.seed
    unit.generation_status = "completed"

# Salva mudanças
project_memory.save_civilizations(project_dir, civs)
```

**Apresente os masters ao Caio:**

> "6 masters de vikings gerados em `assets/civilizations/vikings/units/*/master_sheet.png`. Quais aprovo? Regenerar algum?"

Espere ele responder. Marque `master_approved=True` nos aprovados. Para os reprovados, regenere com:
- Seed nova
- Prompt ajustado com mais ganchos visuais
- Talvez peso de LoRA ajustado

---

## Receita 6 — Gerar animações a partir do master aprovado

**Disparada por:** "agora gera as animações", "expande os masters em frames".

Animações usam `variant_ipadapter.json` com IP-Adapter pesado para manter o personagem visualmente igual ao master.

```python
prompt_builder = prompt_engineer.make_animation_prompt_builder(dna_obj)

for unit in viking.units:
    if not unit.master_approved or not unit.master_sheet_path:
        continue

    master_path = str((project_dir / unit.master_sheet_path).resolve())
    anim_tasks = task_planner.expand_unit_animation_tasks(
        unit=unit,
        civilization=viking,
        dna=dna_obj,
        master_sheet_path=master_path,
        prompt_builder=prompt_builder,
    )

    print(f"{unit.id}: {len(anim_tasks)} frames de animação a gerar")

    for task in anim_tasks:
        wf = wb.build(task,
                      checkpoint_name="sd15_dreamshaper8.safetensors",
                      vae_name="vae-ft-mse-840000-ema-pruned.safetensors")
        try:
            result = client.execute(wf)
            finalize_asset(result.images[0], project_dir / task.target_path,
                           FinalizeOptions(remove_bg=True))
            project_memory.log_generation(project_dir, GenerationLogEntry(...))
        except Exception as e:
            print(f"  Falha em {task.target_path}: {e}")
```

> **Atenção volume:** uma unidade típica = 4 anims × 8 dirs × ~10 frames = 320 frames. Pra 6 unidades, 1920 frames. Isso são ~6h de GPU.
>
> **Estratégia recomendada:** primeiro gere SÓ `idle` de UMA unidade. Mostre ao Caio. Se aprovar, escala. Se não, ajusta workflow/peso de IP-Adapter antes de queimar 6h.

---

## Receita 7 — Adicionar civilização nova a jogo existente

**Disparada por:** "adiciona civilização viking", "nova facção bárbaros", projetos já com DNA congelado.

1. **Leia o estado completo** (não pode quebrar consistência com o que já existe):

```python
meta = project_memory.load_meta(project_dir)
dna = style_dna.load_dna(project_dir)
existing_civs = project_memory.load_civilizations(project_dir)
existing_ids = {c.id for c in existing_civs}
```

2. **Planeje a nova civilização** seguindo `unit_planner.md` e `building_planner.md`. Garanta que:
   - O id é único
   - O estilo respeita o DNA congelado
   - Os papéis cobrem o mínimo (worker, melee, ranged, ...)
   - A paleta secundária a distingue das civs existentes

3. **Apresente ao Caio**. Mostre tabela, peça aprovação.

4. **Adicione** à lista existente e salve:

```python
existing_civs.append(new_civ)
project_memory.save_civilizations(project_dir, existing_civs)
```

5. **Gere os assets** seguindo Receitas 5 e 6.

---

## Receita 8 — Regenerar um asset específico

**Disparada por:** "esse berserker ficou ruim, regenera", "frame 4 do walk SE quebrou".

1. **Encontre a entrada de log original** para recuperar prompt/seed:

```python
last_entry = None
for entry in project_memory.replay_log(project_dir):
    if entry.target_path == "assets/civilizations/vikings/units/berserker/master_sheet.png":
        last_entry = entry  # pega a mais recente
print(last_entry.seed, last_entry.prompt_positive)
```

2. **Decida o ajuste**: nova seed (mesma prompt) ou nova prompt (mesma seed para coerência mínima)?

3. **Gere e sobrescreva**, registrando no log com motivo:

```python
# nova task com seed nova mas mantém path
task = GenerationTask(
    id="regen_" + uuid.uuid4().hex[:6],
    ...,
    seed=last_entry.seed + 1,  # ou totalmente nova
    prompt_positive=ajustado,
    target_path=last_entry.target_path,
)
```

---

## Receita 9 — Status geral do projeto

**Disparada por:** "como está o projeto?", "o que falta gerar?"

```python
summary = project_memory.assets_summary(project_dir)
# Apresenta tabela:
# - X civilizações, Y unidades total (Z prontas), W prédios (V prontos), etc.
```

Pode também rodar via CLI: `tools\status.ps1 -Project fjord_wars`.

---

## Anti-padrões — não faça

- **Não gere paralelo em 6GB.** Uma task por vez. O Comfy é sequencial mesmo.
- **Não mude prompts no meio de uma civilização.** Se descobriu que o prompt de berserker está ruim, REGENERA aquela unit, não mude o prompt das próximas.
- **Não delete o `generation_log.jsonl`.** Ele é a única fonte para regenerar exatamente um asset antigo.
- **Não invente checkpoints.** Use os do `infra/models_manifest.json` que de fato foram baixados.
- **Não comprometa o DNA por um asset chato.** Se a unit não sai bem, ajusta prompt/seed/LoRA dela, não o DNA inteiro.

---

## Como ler o estado quando você não tem certeza

Sempre que houver dúvida de o que existe:

```python
# Lista projetos
for p in PROJECTS.iterdir():
    if p.is_dir() and p.name != "_template":
        print(p.name)

# Estado de um projeto
meta = project_memory.load_meta(p)
dna = style_dna.load_dna(p)              # None se ainda não extraído
civs = project_memory.load_civilizations(p)
buildings = project_memory.load_buildings(p)
terrain = project_memory.load_terrain(p)
plans = project_memory.list_plans(p)
log_tail = list(project_memory.replay_log(p))[-20:]
```

Use isso antes de qualquer ação destrutiva ou que afete coerência.
