"""
main.py — CLI entry point do orquestrador.

Comandos:
  new-project        Cria estrutura de um projeto novo
  extract-dna        Analisa referências e produz partial DNA
  status             Mostra resumo de um projeto
  list-projects      Lista projetos
  health             Checa se o ComfyUI está respondendo
  generate-task      Executa uma GenerationTask específica (JSON)
  smoke              Smoke test do pipeline completo

Os fluxos de planejamento (bootstrap, add-civ etc.) são feitos via Claude Code,
chamando as funções do módulo direto. A CLI cobre operações que se beneficiam
de invocação direta (CI, automação, debug).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.table import Table

from . import project_memory, style_dna as style_dna_mod
from .comfy_client import ComfyClient

app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)

PROJECTS_ROOT = Path(__file__).resolve().parent.parent / "projects"


# ============================================================================
# new-project
# ============================================================================

@app.command()
def new_project(
    name: str = typer.Argument(..., help="Slug do projeto (sem espaços)."),
    display_name: Optional[str] = typer.Option(None, "--display-name"),
    genre: str = typer.Option("rts", "--genre"),
    platform: str = typer.Option("android", "--platform"),
    tone: Optional[str] = typer.Option(None, "--tone"),
    description: Optional[str] = typer.Option(None, "--description"),
    author: Optional[str] = typer.Option(None, "--author"),
):
    """Cria um novo projeto a partir do _template/."""
    try:
        project_dir = project_memory.create_project(
            PROJECTS_ROOT,
            name=name,
            display_name=display_name,
            genre=genre,
            platform=platform,
            tone=tone,
            description=description,
            author=author,
        )
    except (FileExistsError, FileNotFoundError) as e:
        rprint(f"[red]ERRO:[/red] {e}")
        raise typer.Exit(code=1)
    rprint(f"[green]Projeto criado:[/green] {project_dir}")
    rprint(f"  Próximo passo: jogue imagens em {project_dir / 'references'}")
    rprint(f"  Depois rode: orchestrator extract-dna {name}")


# ============================================================================
# extract-dna
# ============================================================================

@app.command()
def extract_dna(
    project: str = typer.Argument(..., help="Slug do projeto."),
    output: Optional[Path] = typer.Option(None, "--output", help="Salva o partial DNA em JSON."),
):
    """Analisa as referências do projeto e imprime o partial DNA (parte computacional)."""
    project_dir = PROJECTS_ROOT / project
    if not project_dir.exists():
        rprint(f"[red]Projeto não encontrado:[/red] {project_dir}")
        raise typer.Exit(code=1)
    refs_dir = project_dir / "references"
    try:
        partial = style_dna_mod.extract_partial_dna(refs_dir)
    except Exception as e:
        rprint(f"[red]Falha:[/red] {e}")
        raise typer.Exit(code=1)
    out_path = output or (project_dir / "style_dna_partial.json")
    out_path.write_text(json.dumps(partial, indent=2, ensure_ascii=False), encoding="utf-8")
    rprint(f"[green]Partial DNA salvo em:[/green] {out_path}")
    rprint(f"Referências analisadas: {partial['_reference_count']}")
    rprint(f"Iluminação detectada: {partial['lighting']['kind']}")
    rprint(f"Paleta dominante: " + ", ".join(c["hex"] for c in partial["palette"][:5]))


# ============================================================================
# status
# ============================================================================

@app.command()
def status(project: str = typer.Argument(..., help="Slug do projeto.")):
    """Mostra resumo de um projeto."""
    project_dir = PROJECTS_ROOT / project
    if not project_dir.exists():
        rprint(f"[red]Projeto não encontrado:[/red] {project_dir}")
        raise typer.Exit(code=1)

    meta = project_memory.load_meta(project_dir)
    dna = style_dna_mod.load_dna(project_dir)
    summary = project_memory.assets_summary(project_dir)

    rprint(f"\n[bold cyan]{meta.display_name}[/bold cyan] ({meta.name})")
    rprint(f"  gênero: {meta.genre} | plataforma: {meta.platform} | tone: {meta.tone or '-'}")
    rprint(f"  DNA: {'congelado v' + str(dna.version) if dna else '[red]ainda não extraído[/red]'}")
    if dna:
        rprint(f"  tokens: {', '.join(dna.style_tokens[:5])}{'...' if len(dna.style_tokens) > 5 else ''}")

    t = Table(title="Conteúdo")
    t.add_column("Categoria")
    t.add_column("Total")
    t.add_column("Pronto")
    t.add_row("Civilizações", str(summary["civilizations"]), "—")
    t.add_row("Unidades", str(summary["units_total"]), str(summary["units_completed"]))
    t.add_row("Construções", str(summary["buildings_total"]), str(summary["buildings_completed"]))
    t.add_row("Terreno (tiles)", str(summary["terrain_total"]), str(summary["terrain_completed"]))
    rprint(t)


# ============================================================================
# list-projects
# ============================================================================

@app.command(name="list-projects")
def list_projects():
    """Lista projetos existentes."""
    if not PROJECTS_ROOT.exists():
        rprint("[yellow]Pasta projects/ não existe ainda.[/yellow]")
        return
    items = [p for p in PROJECTS_ROOT.iterdir() if p.is_dir() and p.name != "_template"]
    if not items:
        rprint("[yellow]Nenhum projeto. Crie com: new-project <nome>[/yellow]")
        return
    t = Table(title="Projetos")
    t.add_column("Nome")
    t.add_column("Display")
    t.add_column("Gênero")
    t.add_column("DNA")
    for p in sorted(items):
        try:
            meta = project_memory.load_meta(p)
            dna = style_dna_mod.load_dna(p)
            dna_str = f"v{dna.version}" if dna else "[red]falta[/red]"
            t.add_row(meta.name, meta.display_name, meta.genre, dna_str)
        except Exception as e:
            t.add_row(p.name, "[red]meta inválida[/red]", "-", str(e))
    rprint(t)


# ============================================================================
# health
# ============================================================================

@app.command()
def health():
    """Verifica se o servidor ComfyUI está respondendo."""
    client = ComfyClient()
    if client.is_alive():
        stats = client.system_stats()
        rprint("[green]ComfyUI ONLINE[/green]")
        rprint(json.dumps(stats, indent=2))
    else:
        rprint("[red]ComfyUI OFFLINE[/red] — inicie com .\\start_pipeline.ps1")
        raise typer.Exit(code=1)


# ============================================================================
# smoke
# ============================================================================

@app.command()
def smoke():
    """Smoke test: gera 1 imagem pequena via probe workflow."""
    from .schemas import GenerationTask, WorkflowKind
    from .workflow_builder import WorkflowBuilder

    client = ComfyClient()
    client.wait_until_alive(max_wait_seconds=10)

    wb = WorkflowBuilder(Path(__file__).resolve().parent.parent / "workflows")
    task = GenerationTask(
        id="smoke",
        asset_kind="ui_portrait",
        workflow=WorkflowKind.STYLE_DNA_PROBE,
        target_ref="test",
        target_path="test_outputs/smoke.png",
        prompt_positive="medieval warrior portrait, fantasy art, clean white background, detailed",
        prompt_negative="blurry, low quality, watermark",
        seed=12345,
        width=512,
        height=512,
        steps=20,
        cfg_scale=7.0,
    )

    wf = wb.build(task, checkpoint_name="sd15_dreamshaper8.safetensors", vae_name="vae-ft-mse-840000-ema-pruned.safetensors")
    out = Path(__file__).resolve().parent.parent / "test_outputs" / "smoke.png"
    rprint(f"Submetendo workflow probe... ({task.workflow.value}, seed={task.seed})")
    saved = client.execute_and_save(wf, out)
    rprint(f"[green]OK[/green] — gerado em {saved}")


if __name__ == "__main__":
    app()
