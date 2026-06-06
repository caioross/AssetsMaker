# Usage — Do conceito ao asset

Depois de rodar o `SETUP.md`, este guia mostra como você usa o sistema para de fato gerar arte de jogo.

Vou ilustrar com um exemplo concreto: criar um RTS viking dark fantasy chamado **"Fjord Wars"**.

---

## Modos de uso

Há duas formas de operar o sistema. Use a que combina mais.

### Modo A — Claude Code como cérebro (recomendado)

Você fala em linguagem natural com o Claude Code dentro da pasta. Ele:

- Lê os `claude-context/*.md` e entende o pipeline
- Conversa com você sobre o conceito do jogo
- Chama as funções do `orchestrator/` diretamente quando precisa
- Edita os JSONs, dispara as gerações, organiza tudo

É o jeito mais natural. Você praticamente não toca em código.

### Modo B — CLI direto (sem Claude Code)

Você roda comandos PowerShell explicitamente. Útil para automação, scripts noturnos, ou pra rodar do nada quando o Claude Code não está acessível.

```powershell
.\tools\new_project.ps1 -Name "fjord_wars"
.\tools\extract_dna.ps1 -Project "fjord_wars"
.\tools\generate.ps1 -Project "fjord_wars" -Category units
```

Por baixo, esses scripts chamam o `orchestrator/main.py` no venv.

> **Posso usar Ollama local em vez do Claude Code?** Sim, em modo "headless". O orquestrador suporta um `--llm ollama:qwen2.5:7b` em vez de chamar Claude. A qualidade do planejamento cai bastante (modelos pequenos têm julgamento de design pior), mas funciona offline e zero-custo. Útil para gerar batches grandes sem supervisão.

---

## Fluxo completo (exemplo: Fjord Wars)

### Passo 1 — Crie o projeto

**No Claude Code:**
> "vamos começar um jogo novo chamado fjord_wars. RTS mobile, viking dark fantasy."

Ele responde criando a estrutura via `tools/new_project.ps1` ou direto. Você termina com `projects/fjord_wars/` populado pelo template.

**CLI puro:**
```powershell
.\tools\new_project.ps1 -Name "fjord_wars" -Genre "rts" -Platform "android" -Tone "dark fantasy"
```

### Passo 2 — Forneça referências

Junte 5-15 imagens que **expressem o que você quer**. Pode ser:

- Screenshots de outros jogos (StarCraft 2 unit shots, AoE 4 building shots, etc.)
- Concept art que te inspirou
- Pinturas, ilustrações, qualquer coisa visualmente coerente

Joga tudo em `projects/fjord_wars/references/`. Dá nome descritivo se quiser (`mood_atmosfera_01.png`, `unidade_referencia_warrior.png`) — opcional.

> **Dica importante:** quanto mais coerentes as referências entre si, mais limpo o DNA vai sair. Se você joga uma pintura medieval realista + um screenshot estilo pixel + um anime, o DNA vai ficar confuso. Pense nisso como o moodboard que você daria a um artista humano.

### Passo 3 — Extraia o Style DNA

**Claude Code:** "extrai o style dna desse projeto"

Ele roda `orchestrator.style_dna.extract()` que:

1. Lê todas as imagens em `references/`
2. Para cada uma, extrai:
   - Paleta dominante (clustering de cores em LAB)
   - Perfil de iluminação (rim light? high contrast? soft?)
   - Peso de silhueta (chunky? slim? articulado?)
   - Tags de material (metal, couro, pedra, magia, sangue, etc.)
3. Cruza informação entre todas e produz o `style_dna.json` consolidado
4. **Te mostra um sumário em texto e te pede confirmação antes de congelar**

Você pode iterar: jogar mais referências, pedir pra ele dar mais peso a uma, etc.

Quando você aprova, o `style_dna.json` fica congelado. Mudanças posteriores precisam ser explícitas (`update-dna` com nova referência ou tweak manual).

### Passo 4 — Bootstrap do plano de assets

**Claude Code:** "monta o plano inicial de assets para o jogo. 2 civilizações pra começar."

Ele chama `task_planner.bootstrap()` que produz:

- `design/civilizations.json` — Nome, lore curta, paleta secundária, traços visuais únicos
- `design/units.json` — Para cada civ, lista de unidades (worker, scout, melee, ranged, siege, hero)
- `design/buildings.json` — Townhall, barracks, defesa, recurso, especial, etc.
- `design/terrain.json` — Tiles base (grass, snow, rock), props (trees, ruins, runestones)
- `design/ui.json` — Portraits, ícones de unidade, ícones de tecnologia

Para cada item, gera **o prompt visual completo já incorporando os tokens do DNA**.

Te mostra um sumário tabular: "X civilizações, Y unidades total, Z prédios, W tiles. ~487 PNGs a gerar. Tempo estimado: ~6h em SD 1.5 batch."

### Passo 5 — Aprovação e ajustes manuais

Antes de queimar 6h de GPU, **você revisa**:

- Os nomes das civilizações fazem sentido?
- Cada unidade tem propósito claro de gameplay?
- O design está coerente com o que você imaginou?

Você pode pedir tweaks ao Claude Code ("muda o nome da civ 1 pra Ulfheðnar", "remove a unidade Berserker, adiciona Skald"). Ele edita os JSONs diretamente.

### Passo 6 — Geração em lote

**Claude Code:** "começa a geração das unidades vikings"

CLI puro:
```powershell
.\tools\generate.ps1 -Project fjord_wars -Civilization vikings -Category units
```

O sistema:

1. Para cada unidade pendente em `design/units.json`:
   - Constrói prompt final (DNA + descrição da unidade + parâmetros de câmera)
   - Submete ao ComfyUI (escolhendo workflow `sd15_character_iso`)
   - Aguarda render (~6-15s em 6GB VRAM com SD 1.5)
   - Passa pelo `rembg`
   - Salva em `assets/civilizations/vikings/units/<nome>/master_sheet.png`
   - Grava no `generation_log.jsonl` (seed, prompt, timestamp, workflow)
2. Faz commit interno do progresso. Se travar no meio, retoma de onde parou.

Você pode rodar em foreground (vê tudo) ou em background:

```powershell
.\tools\generate.ps1 -Project fjord_wars -Category units -Background
```

### Passo 7 — Revisão dos masters e variações

Depois que os masters saem, você abre `assets/civilizations/vikings/units/*/master_sheet.png` e revisa.

- **Adorou todos:** prossegue pra gerar as animações/ângulos.
- **Adorou 4 de 6:** marca os 2 ruins, peça regeneração com prompt ajustado.
- **Adorou 1 de 6:** algo está errado no DNA. Volta no passo 3.

**Claude Code:** "regenera o master do Berserker, mais musculoso, machado duplo, marcas de runa nos braços"

Ele atualiza só essa unidade no JSON e regenera. Os outros não são tocados.

### Passo 8 — Animações e ângulos

Quando os masters estão aprovados:

**Claude Code:** "gera as animações idle/walk/attack/death em 8 direções pros vikings"

Ele usa o `master_sheet.png` aprovado como **input do IP-Adapter**, garantindo que cada frame de cada ângulo mantenha a identidade do master. Resultado:

```
assets/civilizations/vikings/units/berserker/
  ├── master_sheet.png
  ├── animations/
  │   ├── idle/  (8 ângulos × 8 frames = 64 PNGs)
  │   ├── walk/  (8 × 12 = 96)
  │   ├── attack/ (8 × 10 = 80)
  │   └── death/  (8 × 8 = 64)
  └── atlas/
      ├── berserker_idle_sheet.png   # Spritesheet montada
      └── berserker_idle_sheet.json  # Coordenadas
```

> **Limite honesto:** animações 2D puro via IP-Adapter ficam ótimas para idle (poses estáticas com sutilezas) e variações posicionais. Para walk/attack com movimento orgânico real, a qualidade cai — você verá flicker entre frames. Para isso o pipeline 3D-to-2D em Blender é a solução; está documentado em `ARCHITECTURE.md` como caminho de evolução, mas requer modelo 3D, o que sai do escopo da IA pura.

### Passo 9 — Repete pros outros assets

Buildings, terrain, UI — mesmo fluxo. Cada um usa um workflow ComfyUI diferente (`sd15_building_iso`, `sd15_terrain_tile`, `sdxl_ui_portrait`).

### Passo 10 — Você importa na engine

PNGs estão prontos. Estrutura de pastas espelha bem a estrutura típica de um projeto Unity/Godot:

```csharp
// Exemplo Unity
var berserkerIdle = Resources.Load<Texture2D>(
  "civilizations/vikings/units/berserker/atlas/berserker_idle_sheet"
);
```

---

## Operações de manutenção e expansão

### Adicionar uma civilização nova em jogo existente

**Claude Code:** "adiciona civilização Saxões nesse jogo, mais defensiva, escudos grandes, formação fechada"

Ele:
1. Lê `style_dna.json` (não muda)
2. Lê `civilizations.json` existente (pra não duplicar)
3. Expande com a nova civilização respeitando o DNA
4. Te mostra o plano, espera aprovação
5. Gera

### Adicionar item/prop pontual

**Claude Code:** "preciso de uma espada lendária chamada Gungnir, runas brilhantes, item drop de boss"

Ele gera 1 sprite (ou variações) usando o workflow de item, mantendo coerência.

### Atualizar DNA com refinamento

**Claude Code:** "olha essas duas referências novas — quero o jogo mais sombrio, menos saturado, mais detalhe nas armaduras"

Ele:
1. Carrega o DNA atual
2. Analisa as novas referências
3. Propõe merge: "aumenta peso de dark_atmosphere de 0.6 → 0.8, baixa saturation, adiciona token armor_detail"
4. Você confirma
5. DNA atualizado **mas** os assets antigos não são deletados automaticamente — fica registrado um "DNA version 1 → 2 transition"
6. Você decide: regenerar antigos, manter como estão (jogo terá leve evolução visual), ou mix

### Regenerar um sprite específico mantendo coerência

**Claude Code:** "esse atlas do walk do Berserker tem um frame ruim, regenera só o frame 4 do ângulo NE"

Ele recupera seed/prompt do `generation_log.jsonl`, ajusta o que precisa, refaz só aquele frame.

---

## O que **não** fazer

- Não edite `style_dna.json` à mão sem entender — quebra a coerência. Use o comando de update.
- Não mova/renomeie PNGs gerados à mão — o `project_memory.json` aponta pra eles e você quebra o histórico. Use comandos do orquestrador para mover.
- Não rode duas gerações simultâneas no mesmo projeto. 6GB VRAM = uma fila. O sistema bloqueia automaticamente, mas se você forçar com PIDs duplos, vai dar OOM.
- Não gere assets sem antes ter o DNA aprovado. O sistema te avisa, mas se você forçar com `--no-dna`, vai gerar coisas inconsistentes.

---

## Estimativas realistas

| Tarefa | Tempo de máquina (6GB VRAM) | Tempo seu |
|--------|------------------------------|-----------|
| Extrair DNA de 10 refs | 30s | 5 min revisando |
| Bootstrap plano (2 civs, 10 unidades cada) | 1 min (só LLM) | 15-30 min revisando JSON |
| Master sheets de 12 unidades | 5-10 min | 10 min escolhendo bons |
| Animações idle de 12 unidades (8 ângulos × 8 frames) | 2-3h | 30 min curando |
| Prédios principais (8 prédios) | 30-60 min | 10 min |
| Tiles de terreno (12 tiles + props) | 30-45 min | 15 min |
| Pacote completo de 2 civs | ~6-8h GPU | ~3-4h seu |

Compare com contratar um artista: **semanas, $3-15k**. O sistema entrega em um dia de máquina + algumas horas suas, com o ressalva de qualidade-indie-polida (não AAA).
