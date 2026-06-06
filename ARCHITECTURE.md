# Arquitetura do Sistema

Este documento explica **por que** o sistema é assim, **como** as peças conversam, e **onde** ficam as fronteiras de responsabilidade. Sem entender isso, ajustar o pipeline depois fica difícil.

---

## Princípios de design

1. **Separação cérebro/músculo.** O LLM (Claude Code ou Ollama) planeja; o ComfyUI executa. Eles não se misturam: o cérebro nunca renderiza pixel, o músculo nunca decide design.
2. **Tudo dentro da pasta.** Modelos, Python, ComfyUI, venvs, caches. O sistema é "portátil" no sentido de não vazar para `%APPDATA%` ou `C:\Program Files`. Você pode mover a pasta inteira para outro HD/PC e funciona.
3. **Multi-projeto isolado.** Cada jogo tem identidade visual independente (Style DNA). A infra é compartilhada, a identidade não.
4. **Memória persistente em JSON.** Toda decisão importante (DNA, civilizações, seeds usadas, prompts canônicos) vira arquivo versionável. Você pode dar `git init` e ter histórico completo.
5. **Tolerante a falhas de VRAM.** RTX 4050 6GB é apertada para SDXL + ControlNet + IP-Adapter simultâneos. O cliente do ComfyUI degrada elegantemente: reduz batch, troca para SD 1.5, retenta.
6. **Determinístico onde importa.** Seeds são guardadas. Você pode regenerar exatamente o mesmo sprite meses depois.

---

## Camadas

### Camada 1 — Infraestrutura (pasta `infra/`, `ComfyUI/`, `python/`, `venv/`)

Existe para que tudo rode. Scripts PowerShell instalam Python embeddable, clonam ComfyUI, criam venv, instalam extensões e baixam modelos. Você roda uma vez e não pensa mais nisso.

**Componentes:**

- **Python embeddable 3.11** (versão estável para ComfyUI atual)
- **ComfyUI** rodando como servidor HTTP/WS em `localhost:8188`
- **ComfyUI Manager** + custom nodes (IPAdapter Plus, ControlNet Aux, Impact Pack, WAS Node Suite)
- **Modelos baixados** em `ComfyUI/models/`:
  - Checkpoints: SD 1.5 fine-tuned para game art + SDXL Lightning
  - ControlNet: Canny + Lineart + Depth (versões SD 1.5 e SDXL)
  - IP-Adapter: Plus + Plus Face
  - LoRAs: isométrico, game asset, painterly fantasy, dark fantasy
  - VAE + Upscalers (RealESRGAN, 4xUltrasharp)
- **rembg** com modelo `birefnet-general` cacheado localmente

### Camada 2 — Orquestrador (pasta `orchestrator/`)

O código Python que **roda no seu PC** e conecta as peças. Pode ser usado:

- **De forma autônoma** com Ollama local como cérebro (mais lento, mais barato em API, qualidade menor).
- **Como biblioteca chamada pelo Claude Code** — Claude Code lê o código, sabe os schemas, e chama as funções diretamente. Esta é a forma recomendada.

**Módulos:**

| Módulo | Responsabilidade |
|--------|------------------|
| `schemas.py` | Pydantic — define `StyleDNA`, `Project`, `Civilization`, `Unit`, `Building`, `GenerationTask`, etc. Garante que todo JSON trocado seja válido. |
| `style_dna.py` | Lê imagens de referência, extrai paleta, lighting, silhueta, materiais. Persiste em `projects/<game>/style_dna.json`. |
| `project_memory.py` | Lê/escreve toda a memória do projeto. Sabe responder "que unidades a civilização Viking já tem?" sem você precisar lembrar. |
| `task_planner.py` | Recebe um pedido de alto nível ("adiciona civilização Viking") e expande em N tarefas atômicas de geração, respeitando o DNA e o que já existe. |
| `prompt_engineer.py` | Constrói prompts positivos/negativos para cada tarefa, injetando os tokens da DNA, do tipo de asset (unidade vs prédio vs terreno) e da câmera isométrica. |
| `workflow_builder.py` | Carrega um template de `workflows/`, substitui placeholders (prompt, seed, LoRAs, ControlNet inputs) e retorna grafo pronto pra enviar ao ComfyUI. |
| `comfy_client.py` | Cliente do servidor ComfyUI: WebSocket para progresso, REST para submit, download dos PNGs. Trata OOM. |
| `asset_processor.py` | Pega PNG cru, roda rembg, valida transparência, redimensiona/upscale conforme target, monta spritesheets, salva no path correto. |
| `main.py` | CLI: `new-project`, `extract-dna`, `plan`, `generate`, `add-civilization`, etc. |

### Camada 3 — Projetos (pasta `projects/<jogo>/`)

Tudo que é específico de um jogo individual. Você pode ter `projects/viking_rts/`, `projects/cyber_arena/`, `projects/medieval_horror/` ao mesmo tempo.

```
projects/<jogo>/
├── project.yaml              # Metadados (nome, gênero, target, autor)
├── style_dna.json            # A identidade visual congelada
├── references/               # Imagens que você forneceu como referência
│   ├── starcraft_unit.png
│   ├── aoe2_castle.png
│   └── moodboard_*.png
├── design/                   # O que o cérebro planejou
│   ├── civilizations.json    # Lista das civilizações e suas características
│   ├── units.json            # Catálogo de unidades, por civilização
│   ├── buildings.json
│   ├── terrain.json
│   └── ui.json
├── generation_log.jsonl      # Append-only — cada geração registrada
└── assets/                   # Os PNGs prontos para a engine
    ├── civilizations/
    │   └── vikings/
    │       ├── units/
    │       │   └── berserker/
    │       │       ├── master_sheet.png    # Reference sheet
    │       │       ├── animations/
    │       │       │   ├── idle/
    │       │       │   │   ├── idle_NE_000.png
    │       │       │   │   ├── idle_NE_001.png
    │       │       │   │   └── ...
    │       │       │   ├── walk/
    │       │       │   ├── attack/
    │       │       │   └── death/
    │       │       └── atlas/
    │       │           ├── berserker_idle.png   # Spritesheet final
    │       │           └── berserker_idle.json  # Coordenadas
    │       └── (outras unidades)
    │   └── buildings/
    │       └── longhouse/
    ├── terrain/
    │   ├── tiles/
    │   └── decoration/
    └── ui/
        ├── portraits/
        └── icons/
```

---

## Os fluxos principais

### Fluxo 1 — Bootstrap de um novo jogo

```
USUÁRIO: "Quero criar um RTS viking dark fantasy. Olha essas referências."
   │
   ├─ joga imagens em projects/viking_rts/references/
   │
   ▼
Claude Code (ou tools/new_project.ps1):
  1. Cria projects/viking_rts/ pela cópia do _template
  2. Chama orchestrator.style_dna.extract(references/)
     → analisa paleta, lighting, materiais, silhueta
     → grava style_dna.json
  3. Chama orchestrator.task_planner.bootstrap()
     → "para um RTS viking dark fantasy, faça um plano inicial:
        2 civilizações (Vikings invasores, Saxões defensores),
        6 unidades cada com 4 animações em 8 ângulos,
        8 prédios, 12 tiles de terreno, ..."
     → grava design/civilizations.json, units.json, etc.
  4. Imprime resumo: "Plano gerado. 487 sprites a serem renderizados.
     Tempo estimado: 6h em batches noturnos. Confirma?"
```

### Fluxo 2 — Geração em lote (executar o plano)

```
USUÁRIO: "tools/generate.ps1 --project viking_rts --category units"
   │
   ▼
orchestrator.main generate
  para cada task em design/units.json com status=pending:
    1. prompt_engineer.build(task, style_dna)
       → prompt positivo/negativo + escolha de LoRAs + ControlNet
    2. workflow_builder.from_template("sd15_character_iso", inputs)
       → grafo ComfyUI pronto
    3. comfy_client.submit(grafo)
       → aguarda WebSocket, baixa PNG
    4. asset_processor.finalize(png, task.target_path)
       → rembg, ajuste, salva no path final
    5. project_memory.mark_completed(task, seed, timestamp)
       → registra em generation_log.jsonl
```

### Fluxo 3 — Adicionar conteúdo depois (6 meses depois)

```
USUÁRIO (no Claude Code, dentro de viking_rts/):
"adiciona uma nova civilização: Bárbaros das Estepes"
   │
   ▼
Claude Code:
  1. Lê projects/viking_rts/style_dna.json
  2. Lê design/civilizations.json existentes (entende o que já existe)
  3. Chama task_planner.add_civilization("Bárbaros das Estepes")
     → expande em unidades/prédios coerentes com o DNA e o gênero
  4. Mostra o plano, espera você aprovar
  5. Executa generate
```

Como o `style_dna.json` é congelado desde a primeira geração, **o sprite de hoje e o sprite de daqui a 1 ano usam exatamente os mesmos tokens de estilo, os mesmos LoRAs, a mesma paleta e os mesmos parâmetros de câmera.**

---

## Por que isso resolve as limitações que existiriam

| Problema clássico | Como o sistema lida |
|-------------------|---------------------|
| **Consistência entre sprites** | DNA persistido + IP-Adapter forçando aderência à reference sheet por unidade |
| **Ângulo isométrico variando** | ControlNet Depth/Canny com guia pré-renderizado (perspectiva 2:1 fixa) |
| **Esquecer o estilo entre sessões** | `style_dna.json` versionado + Claude Code lê em toda sessão |
| **VRAM 6GB apertada** | SD 1.5 default, SDXL apenas para hero shots, modo lowvram, fila sequencial |
| **Organização caótica de arquivos** | Estrutura imposta pelos schemas + `asset_processor` impossível de quebrar |
| **Refazer a mesma unidade meses depois** | Seeds + prompts armazenados em `generation_log.jsonl` |
| **Misturar estilos entre jogos diferentes** | Projetos completamente isolados em pastas separadas |

---

## O que o sistema **não** resolve (transparência radical)

- **Animação 3D-rigged.** Para animações realmente fluidas (idle respirando, walk com peso, attack com windup) o caminho profissional é modelar/riggar em 3D e renderizar em 8 ângulos no Blender. O sistema tem stubs para esse pipeline mas requer modelos 3D, e gerar modelos 3D bons via IA (Hunyuan3D etc.) ainda não dá game-ready out of the box. **Estratégia recomendada**: animações 2D frame-by-frame por IP-Adapter (boa para idle simples e variações estáticas); para combate de verdade, gere chaves manuais ou contrate um animador 2D pontual para frames-chave.
- **Qualidade nível Blizzard.** SD/SDXL atinge "indie polido" facilmente; "AAA studio" exige curadoria humana ainda. O sistema acelera 10x, não 100x.
- **Som, música, código de jogo.** Fora do escopo. Existem pipelines análogos (Audiocraft, etc.) mas não estão neste sistema.

Esses limites estão claros no `USAGE.md` quando você vai gerar o primeiro asset.

---

## Para onde o Claude Code entra

Quando você abrir esta pasta no Claude Code, ele lê `claude-context/CLAUDE.md` e ganha:

- Mapa mental do projeto (esta arquitetura)
- Convenções de naming, paths, schemas
- Comandos comuns de PowerShell e Python prontos
- Os system prompts canônicos para assumir papel de Diretor de Arte / Planejador de Unidades / Analisador de Estilo

A partir daí, você conversa em alto nível ("adiciona um item lendário", "varia esse berserker em 3 versões de armadura", "esse tile ficou desalinhado, regenera com seed parecida") e ele executa via o orquestrador.

Esta é a **diferença de classe** entre rodar um Ollama 9B local fazendo design e usar o Claude Code: a qualidade do planejamento sobe drasticamente, e você ganha um colaborador real em vez de um gerador de texto.
