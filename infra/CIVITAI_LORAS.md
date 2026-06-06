# LoRAs do Civitai — download manual

LoRAs com licença comercial-amigável ficam no Civitai (não tem mirror público). Como o download exige API token e a licença varia, o sistema **não baixa automaticamente** — você escolhe e baixa manualmente.

---

## Como obter um API token (gratuito)

1. Crie conta em https://civitai.com
2. Vá em **Account Settings → API Keys → Add API Key**
3. Copie o token. Guarde em variável de ambiente:

```powershell
[Environment]::SetEnvironmentVariable('CIVITAI_TOKEN', 'sua_chave_aqui', 'User')
```

(Feche e reabra o PowerShell para o token virar disponível.)

---

## LoRAs recomendados para este pipeline

Pesquise no Civitai e filtre por **License → Commercial use allowed** antes de baixar. Os exemplos abaixo são bons pontos de partida; **verifique a licença** antes de usar em jogo comercial.

### Para SD 1.5 (isométrico / game asset)

| LoRA | Busca no Civitai | Trigger words típicos | Destino |
|------|------------------|----------------------|---------|
| Isometric Asset / Game Asset | "isometric game asset", "isometric tile" | `isometric`, `game asset`, `clean background` | `ComfyUI/models/loras/iso_asset_sd15.safetensors` |
| Game Building / Architecture | "fantasy building", "iso building", "game ui icon" | `fantasy building`, `game architecture` | `ComfyUI/models/loras/iso_building_sd15.safetensors` |
| Painterly Fantasy | "painterly", "blizzard style", "warcraft style" | `painterly`, `stylized fantasy` | `ComfyUI/models/loras/painterly_sd15.safetensors` |
| Dark Fantasy Atmosphere | "dark fantasy", "diablo style", "gothic" | `dark fantasy`, `grim`, `cinematic lighting` | `ComfyUI/models/loras/dark_fantasy_sd15.safetensors` |

### Para SDXL (hero shots / UI premium)

| LoRA | Busca no Civitai | Destino |
|------|------------------|---------|
| Game Icon / UI XL | "game icon xl", "ui icon" | `ComfyUI/models/loras/game_icon_xl.safetensors` |
| Stylized Character XL | "stylized character xl", "rpg character" | `ComfyUI/models/loras/stylized_char_xl.safetensors` |

---

## Download manual via PowerShell

```powershell
$token = $env:CIVITAI_TOKEN
$modelId = 'COLE_ID_AQUI'  # ID numérico da versão (não do modelo)
$out = 'E:\Projetos\SISTEMA AssetsMaker\ComfyUI\models\loras\meu_lora.safetensors'

Invoke-WebRequest -Uri "https://civitai.com/api/download/models/$modelId" `
                  -Headers @{ Authorization = "Bearer $token" } `
                  -OutFile $out
```

O ID da versão aparece na URL da página do LoRA (depois de `/models/<modelId>?modelVersionId=<id>`).

---

## Depois de baixar

Atualize o `infra/models_manifest.json` substituindo o placeholder pelo arquivo real (mantém o `destination`, troca o `url` para o link Civitai válido e ajusta `size_bytes`). Isso garante que se um dia outra máquina rodar `05_download_models.ps1`, o LoRA seja considerado "presente" e não tentado.

E informe ao orquestrador que o LoRA existe — edite `claude-context/CLAUDE.md` adicionando o trigger word à lista de LoRAs disponíveis. O Claude Code passará a usar automaticamente quando o estilo do projeto pedir.

---

## Atenção a licenças

Civitai mistura LoRAs com licenças diferentes. Antes de usar em **jogo comercial** ou em projeto que possa ser monetizado:

- Filtre por "Commercial use allowed" no Civitai
- Leia a aba "License" / "Permissions" do modelo
- Alguns proíbem geração de imagens vendidas, outros só proíbem revender o LoRA, outros liberam tudo. Não há um padrão.

Quando em dúvida, prefira LoRAs do HuggingFace com licença `CreativeML Open RAIL-M` (essa é a do SD base e permite uso comercial).
