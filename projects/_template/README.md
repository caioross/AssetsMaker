# Project Template

Este diretório é a base copiada pelo `orchestrator.project_memory.create_project()` quando você cria um jogo novo. **Não edite nada aqui diretamente** — toda alteração afeta projetos futuros.

## Estrutura criada para cada projeto

```
projects/<jogo>/
├── project.yaml              Metadados básicos
├── style_dna.json            (criado depois de extract-dna)
├── references/               Você joga imagens aqui
├── design/
│   ├── civilizations.json
│   ├── buildings.json
│   ├── terrain.json
│   ├── ui.json
│   └── plans/                Histórico de planos do diretor
├── generation_log.jsonl      Log append-only de tudo que foi gerado
└── assets/                   PNGs prontos para a engine
    ├── civilizations/
    ├── terrain/
    └── ui/
```

## Como adicionar um arquivo padrão ao template

1. Crie/edite o arquivo aqui em `projects/_template/`
2. Todos os projetos criados a partir daí o terão
3. Projetos já existentes precisam receber o arquivo manualmente
