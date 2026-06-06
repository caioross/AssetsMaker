"""
smoke_test.py — chamado pelo 06_verify_install.ps1 após o setup.

Confirma que: venv + torch+cuda + ComfyUI online + workflow_builder + comfy_client
formam um pipeline funcional. Gera uma imagem 512x512 simples e termina.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.comfy_client import ComfyClient  # noqa: E402
from orchestrator.schemas import GenerationTask, WorkflowKind  # noqa: E402
from orchestrator.workflow_builder import WorkflowBuilder  # noqa: E402


def main() -> int:
    print("== Smoke test do pipeline ==")
    client = ComfyClient()
    print("Aguardando ComfyUI...")
    client.wait_until_alive(max_wait_seconds=30)
    print("ComfyUI ONLINE")

    wb = WorkflowBuilder(ROOT / "workflows")
    task = GenerationTask(
        id="smoke",
        asset_kind="ui_portrait",
        workflow=WorkflowKind.STYLE_DNA_PROBE,
        target_ref="smoke",
        target_path="test_outputs/sanity_check.png",
        prompt_positive="a knight in armor, fantasy concept art, simple, detailed, clean white background",
        prompt_negative="blurry, watermark, low quality, deformed",
        seed=42,
        width=512,
        height=512,
        steps=20,
        cfg_scale=7.0,
    )

    wf = wb.build(
        task,
        checkpoint_name="sd15_dreamshaper8.safetensors",
        vae_name="vae-ft-mse-840000-ema-pruned.safetensors",
    )

    out = ROOT / "test_outputs" / "sanity_check.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Gerando em {out}...")
    saved = client.execute_and_save(wf, out)
    size = saved.stat().st_size
    print(f"OK — arquivo gerado ({size} bytes)")
    if size < 1024:
        print("AVISO: arquivo muito pequeno — geração pode ter falhado.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
