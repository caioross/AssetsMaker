# NEXT_STEPS — O que fazer agora

A infraestrutura, o orquestrador, os workflows, o template de projeto, e os guias do Claude Code estão prontos. **Você ainda não tem ComfyUI nem modelos instalados** — isso é feito pelo seu PC executando os scripts.

Este documento é o roteiro literal do "primeiro dia". Siga em ordem.

---

## Fase 1 — Instalação (1 sessão de ~1h, em grande parte automática)

### Passo 1.1 — Confira pré-requisitos

```powershell
# Em qualquer terminal
git --version           # precisa estar > 2.30
nvidia-smi              # precisa mostrar sua RTX 4050 e driver 555+
```

Se falhou algo:
- **Sem git:** https://git-scm.com/download/win — Next Next Finish.
- **Driver NVIDIA antigo:** https://www.nvidia.com/Download/index.aspx — pegue Game Ready ou Studio mais recente.

### Passo 1.2 — Permita execução de scripts (PowerShell admin, uma vez)

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Confirma com `Y`.

### Passo 1.3 — Rode o setup mestre

```powershell
cd "E:\Projetos\SISTEMA AssetsMaker"
.\setup.ps1
```

Vai demorar. Pode ir tomar café. Os 6 instaladores rodam em sequência:

1. Python embeddable (1 min)
2. ComfyUI clone (2 min)
3. venv + torch + cuda 12.4 + deps (5-10 min — `torch` é grande)
4. Custom nodes do ComfyUI (2 min)
5. Modelos do HuggingFace (20-60 min — depende da internet)
6. Smoke test (2 min)

No final você deve ver "SETUP COMPLETO" + um PNG em `test_outputs\sanity_check.png` que prova que o pipeline rodou ponta-a-ponta.

### Passo 1.4 — Se o smoke test falhar

A vasta maioria dos problemas é uma destas:

- **CUDA não detectado** → driver NVIDIA precisa atualizar
- **OOM no smoke test** → edite `infra/installers/06_verify_install.ps1` e troque `--medvram` por `--lowvram`
- **Download de um modelo falhou no meio** → `.\infra\installers\05_download_models.ps1 -OnlyMissing` tenta de novo

O log fica em `logs/setup_*.log`.

---

## Fase 2 — Validação rápida com Claude Code (15 min)

Abra a pasta no Claude Code:

```powershell
cd "E:\Projetos\SISTEMA AssetsMaker"
claude
```

Cole a mensagem inicial:

```
Leia claude-context/CLAUDE.md primeiro, depois pipeline-guide.md.
Confirma que entendeu o sistema, sua função e onde estão as coisas.
Lista pra mim quais modelos estão instalados em ComfyUI/models/.
Sobe o ComfyUI em background e roda um health check via tools/health.ps1.
```

Ele deve responder com:
- Resumo do papel dele (Diretor de Arte + Engenheiro)
- Lista dos modelos baixados
- ComfyUI rodando + JSON do `system_stats`

**Se algo aqui der errado, é mais fácil acertar antes de criar projeto real do que depois.**

---

## Fase 3 — Primeiro projeto real (1-2 sessões)

### Passo 3.1 — Escolha o jogo

Pense em UM jogo concreto pra começar. Não dois. Concreto: nome, gênero, tom, 3 frases de descrição. Exemplo:

> **Fjord Wars** — RTS mobile, dark fantasy viking. Civilizações inspiradas em nórdicos, saxões e bárbaros das estepes. Tom sombrio, foco em táticas de tribo vs tribo. Estética inspirada em StarCraft 2 + Darkest Dungeon + concept arts da expansão de Diablo IV.

### Passo 3.2 — Junte referências

5-15 imagens **coerentes entre si**. Pode ser:

- Screenshots dos jogos que te inspiram
- Concept art que encontrou
- Pinturas/ilustrações

Qualidade > quantidade. Joga em `projects/fjord_wars/references/` (a pasta nasce quando você criar o projeto no próximo passo).

### Passo 3.3 — Crie o projeto no Claude Code

```
Vamos criar o jogo "Fjord Wars".
Gênero: rts, plataforma: android, tom: dark fantasy viking.
Descrição: <cola sua descrição de 3 frases>.
Cria o projeto e me diz onde devo jogar as referências.
```

Ele executa `tools\new_project.ps1` e te confirma o path. Joga suas imagens lá.

### Passo 3.4 — Extraia DNA

```
Já joguei as referências. Extrai o style DNA.
```

Ele:
1. Roda análise computacional (paleta, lighting, silhueta)
2. Lê as imagens visualmente
3. Propõe `style_tokens`, `negative_tokens`, `pinned_loras`, etc.
4. Te mostra resumo e pede confirmação
5. Você aprova → ele congela como v1

### Passo 3.5 — Smoke test do DNA antes de queimar GPU

```
Antes de gerar tudo, faz um teste do DNA: gera 1 imagem de um guerreiro genérico
com o style DNA atual. Quero ver se o estilo aparece.
```

Ele gera 1 PNG via workflow `style_dna_probe`. Você abre, julga. Se estiver longe do que quer, ajusta tokens/LoRAs e refaz. **NÃO PROSSIGA** sem aprovar este resultado — todo o resto depende dele.

### Passo 3.6 — Bootstrap do catálogo (sem gerar ainda)

```
Planeja: 2 civilizações iniciais (vikings + saxões),
6 unidades cada cobrindo papéis básicos, 8 prédios cada.
Mostra a tabela antes de gravar.
```

Ele te mostra o catálogo proposto. Você itera ("muda nome de tal", "tira tal unidade", "adiciona um hero"), e quando estiver bom, ele grava em `design/civilizations.json` e `design/buildings.json`.

### Passo 3.7 — Gera masters (só masters, sem animação ainda)

```
Gera os 12 master sheets das unidades das duas civs.
Só os masters por enquanto.
```

~15-20 min de GPU. No final ele te apresenta todos. Você aprova/reprova/regenera.

### Passo 3.8 — Decisão estratégica antes de animar

**Animações vão demorar 6-8h e gastar 6h de GPU.** Antes:

1. Os masters aprovados estão visualmente coerentes entre si? Se sim, prossegue.
2. Os 8 ângulos do mesmo personagem vão funcionar com IP-Adapter? **Faz 1 unidade primeiro**: pede pro Claude gerar SÓ idle de UMA unidade em 8 ângulos. Vê se o personagem se mantém. Se sim, libera as outras. Se a consistência cai muito, ajusta peso de IP-Adapter (sobe pra 0.95) e refaz.

```
Antes de queimar 6h, gera só idle do berserker em 8 direções. Quero validar.
```

### Passo 3.9 — Libera o restante (provavelmente overnight)

```
Aprovei. Gera todas as animações de todas as unidades das duas civs em background.
Loga o progresso pra eu acompanhar.
```

Ele inicia. Você vai dormir.

### Passo 3.10 — Prédios e terreno

Depois dos personagens, prédios e terrenos são mais rápidos e independentes. Pode rodar em paralelo (mesmo projeto, fila sequencial no Comfy).

---

## Fase 4 — Polimento e iteração (contínuo)

Quando o Caio quiser **adicionar conteúdo** depois (próxima civilização, item lendário, mapa novo):

```
Adiciona civilização Bárbaros das Estepes ao fjord_wars,
mais focada em cavalaria, paleta mais quente (tons de areia e ferrugem).
```

O Claude Code lê o DNA congelado, lê o que já existe, planeja em coerência, te mostra, executa.

Quando o Caio quiser **expandir o estilo do jogo**:

```
Olha essas 3 referências novas — quero o jogo mais sombrio e com mais magia
visível em runas brilhando. Atualiza o DNA.
```

Ele propõe diff de DNA (v1 → v2), você aprova, ele grava nova versão mantendo histórico. Assets antigos ficam (marcados como DNA v1). Novos assets nascem com DNA v2.

---

## Coisas a fazer no Claude Code para refinar o sistema

Quando o sistema rodar mas você quiser melhorá-lo (sua frase: "depois eu aprimoro no claudecode"), alguns alvos óbvios:

1. **Workflows ComfyUI melhores.** Abra cada `workflows/*.json` no UI do ComfyUI, ajuste, exporte de novo. Substitua valores estáticos por `@@PLACEHOLDER@@` correspondente do `workflow_builder.py`. Workflows top de Civitai/GitHub frequentemente vêm com nodes que você pode portar.

2. **LoRAs específicos do Civitai.** Leia `infra/CIVITAI_LORAS.md`, busque LoRAs comerciais-amigáveis que casem com o estilo do jogo X, baixe, registre no `models_manifest.json`. Refine o `style_dna.json` para apontar pra eles.

3. **Pipeline de animação melhor.** O atual usa IP-Adapter puro. Para melhor consistência em walk/attack, considere:
   - AnimateDiff (já instalado, ver `ComfyUI-AnimateDiff-Evolved` em custom nodes)
   - Reference-only ControlNet (precisa adicionar ao manifesto)
   - Híbrido 3D→2D via Blender (escopo maior; veja `ARCHITECTURE.md`)

4. **UI dashboard.** Crie um HTML simples em `tools/dashboard.html` que liste projetos, status, miniaturas dos assets. O orquestrador já tem `assets_summary()` — só amarrar.

5. **Background batching com retry inteligente.** O atual `for task in tasks` é simples. Pode evoluir para fila persistente em SQLite que retoma de onde parou após reboot.

6. **Anti-drift de IP-Adapter.** Para 8 ângulos da mesma unit, em vez de só passar master, gere uma reference sheet com múltiplos ângulos primeiro e use ela como input. Reduz drift drasticamente.

---

## Quanto isso vai custar (esperado)

- **Setup (uma vez):** Tempo seu — ~1h ativa + ~1h passiva (download).
- **Por jogo:** 1 dia de planejamento + 1-2 noites de GPU + ~4h de curadoria.
- **API do Claude Code:** poucos dólares por jogo (planejamento é texto, é barato).
- **Infraestrutura:** $0/mês. Tudo local.

Comparativo: contratar um artista indie pra mesmo escopo custaria $3-15k e levaria semanas.

---

## O que ainda não está pronto e fica de exercício

- **Pipeline 3D→2D (Blender):** documentado em `ARCHITECTURE.md` como caminho de evolução para animação profissional. Requer instalar Blender e escrever scripts `bpy`. Não está no escopo desta entrega inicial; é o passo seguinte se você quiser qualidade de animação acima do que IP-Adapter entrega.
- **Geração de áudio/música:** fora de escopo. Existe pipeline análogo (Audiocraft, MusicGen) mas não foi incluído.
- **Tile-safe seamless terrains:** os tiles são gerados como sprites; para tileable real (sem costura) precisa adicionar workflow específico com SD em modo seamless ou pós-processo de blending de bordas. Item de melhoria.
- **Pipeline de variantes em lote (skin, cores, weapons).** O `task_planner` tem só master + animação. Adicionar `expand_variants_task()` é direto se quiser várias versões da mesma unit com armadura/cor diferente.

Esses pontos estão registrados como "limites honestos" para você não ter surpresa.

---

## Resumo de "o que você tem agora"

✅ Estrutura completa de pastas e código
✅ 6 instaladores PowerShell em sequência
✅ Manifestos de modelos e extensões
✅ Orquestrador Python completo (schemas, DNA, memory, planner, prompt engineer, comfy client, asset processor, CLI)
✅ 6 templates de workflow ComfyUI (com placeholders)
✅ 5 atalhos PowerShell em `tools/`
✅ Template de projeto multi-jogo
✅ Briefing completo do Claude Code (CLAUDE.md + pipeline-guide.md + 4 system prompts canônicos)
✅ Documentação raiz (README, ARCHITECTURE, SETUP, USAGE)
✅ Este NEXT_STEPS e um `.gitignore` pronto

⏳ ComfyUI e modelos só serão **instalados quando você rodar `setup.ps1`** (eu não tinha como baixar 15GB pra você).

⏳ Os ajustes finos (LoRAs específicos do Civitai, workflows refinados, melhorias de animação) ficam pra você fazer no Claude Code com base no que esse sistema já provê.

Boa jornada. Quando rodar `setup.ps1` e abrir no Claude Code, ele já estará pronto pra ser seu Diretor de Arte.
