# Setup — Instalação completa

Este documento te leva de "pasta vazia" para "sistema pronto para gerar o primeiro sprite". Reserva ~1h de relógio (a maior parte é download de modelos rodando sozinho).

---

## Pré-requisitos

| Item | Detalhe |
|------|---------|
| **Windows 10/11** | Testado em ambos |
| **GPU NVIDIA** | RTX 4050 6GB é o suficiente (este sistema foi calibrado pra isso). RTX 3060 12GB ou superior roda mais relaxado. |
| **Driver NVIDIA recente** | 555+ (CUDA 12.4+). Atualize antes se estiver muito antigo. |
| **~35 GB de disco livre** | ComfyUI + modelos + cache. SSD recomendado mas não obrigatório. |
| **Conexão estável** | Para baixar ~15-20 GB de modelos. |
| **PowerShell 5+** | Já vem com Windows 10/11. |
| **Git** | https://git-scm.com/download/win — necessário pra clonar ComfyUI e extensões. |

> **Não precisa instalar Python no sistema.** O setup baixa um Python embeddable dedicado para esta pasta. Não vai conflitar com Python que você já tenha.

---

## Passo a passo

### 1. Abra PowerShell **como administrador**

Botão Iniciar → digite "PowerShell" → clique direito → "Executar como administrador".

> Admin é necessário só na primeira vez, para habilitar execução de scripts (próximo passo). Depois disso você pode usar PowerShell normal.

### 2. Permita execução de scripts (apenas uma vez)

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Confirma com `Y`. Isso permite scripts locais não-assinados (como os nossos) sem desbloquear scripts da internet.

### 3. Navegue para a pasta do projeto

```powershell
cd "E:\Projetos\SISTEMA AssetsMaker"
```

### 4. Rode o setup mestre

```powershell
.\setup.ps1
```

Ele vai executar, em ordem:

| Etapa | O que faz | Tempo aproximado |
|-------|-----------|------------------|
| `01_install_python.ps1` | Baixa Python 3.11 embeddable em `python/` | 1 min |
| `02_install_comfyui.ps1` | Clona ComfyUI em `ComfyUI/`, configura para usar Python local | 2 min |
| `03_install_python_env.ps1` | Cria `venv/`, instala torch+cuda, rembg, pydantic, websocket-client, etc. | 5-10 min |
| `04_install_comfy_extensions.ps1` | Clona ComfyUI Manager + IPAdapter Plus + ControlNet Aux + Impact Pack | 2 min |
| `05_download_models.ps1` | **A demorada** — baixa SD 1.5, SDXL Lightning, ControlNets, IP-Adapter, LoRAs | 20-60 min (depende da internet) |
| `06_verify_install.ps1` | Smoke test: sobe ComfyUI, gera 1 imagem de teste, mata o processo | 2 min |

Você pode rodar cada etapa individualmente se quiser controle (todas estão em `infra/installers/`).

### 5. Verifique que deu certo

Ao final do `setup.ps1`, você deve ver:

```
SETUP COMPLETO
✓ Python 3.11 instalado em python/
✓ ComfyUI clonado em ComfyUI/
✓ Venv criada em venv/ com 47 pacotes
✓ 4 custom nodes instalados
✓ 12 modelos baixados (15.2 GB)
✓ Smoke test passou — sprite gerado em test_outputs/sanity_check.png

Próximo passo: leia USAGE.md ou abra esta pasta no Claude Code.
```

Se algum passo falhar, ele para na hora e te diz qual foi. O log completo fica em `logs/setup_<timestamp>.log`.

---

## Configurando o Claude Code (opcional mas recomendado)

Após o setup técnico, abrir esta pasta no Claude Code te dá um colaborador que já entende o sistema:

```powershell
cd "E:\Projetos\SISTEMA AssetsMaker"
claude
```

Na primeira mensagem, peça: "leia `claude-context/CLAUDE.md` e me ajude a criar o primeiro projeto".

Ele lê todos os guias, entende o pipeline, e te conduz no primeiro fluxo.

---

## Tem que rodar como administrador depois?

Não. Só o passo 2 (`Set-ExecutionPolicy`). Daí em diante PowerShell normal está ok.

---

## Como atualizo os modelos / extensões depois?

```powershell
.\infra\installers\04_install_comfy_extensions.ps1 -Update
.\infra\installers\05_download_models.ps1 -OnlyMissing
```

O primeiro faz `git pull` em cada extensão. O segundo baixa só o que está no manifesto e ainda não foi baixado (útil quando você adiciona um LoRA novo ao manifesto).

---

## Como remover tudo?

Apaga a pasta. Sério, é isso. Nada vaza para o sistema.

---

## Problemas comuns

**"Cannot be loaded because running scripts is disabled on this system"**
Você esqueceu o passo 2. Volta nele.

**"git: command not found"**
Você não instalou Git. Vai em https://git-scm.com/download/win, instala, reabre o PowerShell.

**Download de modelo falha no meio**
Roda de novo. O `05_download_models.ps1` é idempotente: pula o que já tem.

**Erro CUDA no smoke test**
Driver NVIDIA está antigo. Atualiza para 555+. Em casos raros, instala manualmente CUDA 12.4.

**OOM (Out of Memory) durante smoke test**
Já deveria ser raro, mas se acontecer abre `ComfyUI/start_comfyui.ps1` e troca `--medvram` por `--lowvram` na linha de comando.

**ComfyUI não sobe**
Cheque `logs/comfy_*.log`. Geralmente é Python errado encontrado. Roda `01_install_python.ps1` de novo.
