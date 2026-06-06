"""
comfy_client.py — cliente do servidor ComfyUI local.

Responsabilidades:
- Health check (sobe e responde?)
- Submeter um workflow (grafo JSON formato API)
- Monitorar progresso via WebSocket
- Baixar o(s) PNG(s) resultantes
- Cancelar jobs / clear queue

Tratamento de erros:
- OOM (CUDA out of memory) → dispara callback para o caller tentar reduzir parâmetros
- Server offline → retry com backoff
- Workflow inválido (ex: nó inexistente) → erro claro pra debugar template
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import requests
import websocket  # websocket-client


# ============================================================================
# Tipos
# ============================================================================

@dataclass
class GenerationResult:
    """O que volta quando um workflow termina com sucesso."""
    prompt_id: str
    images: list[bytes] = field(default_factory=list)
    image_filenames: list[str] = field(default_factory=list)
    runtime_seconds: float = 0.0
    node_outputs: dict = field(default_factory=dict)


class ComfyError(RuntimeError):
    """Erro genérico do ComfyUI."""


class ComfyOOMError(ComfyError):
    """Sinaliza out-of-memory CUDA — caller deve degradar gracefully."""


# ============================================================================
# Cliente
# ============================================================================

class ComfyClient:
    def __init__(
        self,
        server: str = "127.0.0.1:8188",
        timeout_seconds: float = 600.0,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ):
        self.server = server
        self.timeout = timeout_seconds
        self.progress_callback = progress_callback or (lambda _msg: None)
        self.client_id = str(uuid.uuid4())

    # --- health ------------------------------------------------------------

    def is_alive(self) -> bool:
        try:
            r = requests.get(f"http://{self.server}/system_stats", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def wait_until_alive(self, max_wait_seconds: float = 60.0) -> None:
        start = time.time()
        while time.time() - start < max_wait_seconds:
            if self.is_alive():
                return
            time.sleep(2.0)
        raise ComfyError(
            f"ComfyUI não respondeu em {max_wait_seconds}s. "
            f"Verifique se está rodando em http://{self.server}"
        )

    def system_stats(self) -> dict:
        r = requests.get(f"http://{self.server}/system_stats", timeout=5.0)
        r.raise_for_status()
        return r.json()

    # --- queue management --------------------------------------------------

    def queue_status(self) -> dict:
        r = requests.get(f"http://{self.server}/queue", timeout=5.0)
        r.raise_for_status()
        return r.json()

    def clear_queue(self) -> None:
        requests.post(
            f"http://{self.server}/queue",
            json={"clear": True},
            timeout=5.0,
        )

    def cancel_running(self) -> None:
        requests.post(f"http://{self.server}/interrupt", timeout=5.0)

    # --- submissão ---------------------------------------------------------

    def submit(self, workflow: dict) -> str:
        """Submete um workflow. Retorna prompt_id."""
        payload = {"prompt": workflow, "client_id": self.client_id}
        r = requests.post(
            f"http://{self.server}/prompt",
            json=payload,
            timeout=30.0,
        )
        if r.status_code != 200:
            raise ComfyError(
                f"Submit falhou (HTTP {r.status_code}): {r.text}"
            )
        return r.json()["prompt_id"]

    def history(self, prompt_id: str) -> dict:
        r = requests.get(f"http://{self.server}/history/{prompt_id}", timeout=10.0)
        r.raise_for_status()
        return r.json()

    # --- execução completa: submit + monitor + download -------------------

    def execute(self, workflow: dict) -> GenerationResult:
        """
        Submete o workflow, monitora via WebSocket até completar,
        baixa as imagens resultantes.
        """
        start = time.time()
        prompt_id = self.submit(workflow)
        self._monitor(prompt_id)
        result = self._collect_outputs(prompt_id)
        result.runtime_seconds = time.time() - start
        return result

    # --- monitor via WebSocket --------------------------------------------

    def _monitor(self, prompt_id: str) -> None:
        ws_url = f"ws://{self.server}/ws?clientId={self.client_id}"
        ws = websocket.WebSocket()
        ws.settimeout(self.timeout)
        try:
            ws.connect(ws_url)
            while True:
                msg = ws.recv()
                if isinstance(msg, bytes):
                    # Pode ser preview (binário). Ignora aqui.
                    continue
                data = json.loads(msg)
                self.progress_callback(data)
                mtype = data.get("type")
                if mtype == "execution_error":
                    err = data.get("data", {})
                    text = json.dumps(err)
                    if "CUDA out of memory" in text or "OutOfMemoryError" in text:
                        raise ComfyOOMError(text)
                    raise ComfyError(f"Erro de execução: {text}")
                if mtype == "executing":
                    payload = data.get("data", {})
                    if payload.get("node") is None and payload.get("prompt_id") == prompt_id:
                        # Execução do nosso prompt terminou
                        return
        finally:
            try:
                ws.close()
            except Exception:
                pass

    # --- coleta de outputs -------------------------------------------------

    def _collect_outputs(self, prompt_id: str) -> GenerationResult:
        hist = self.history(prompt_id)
        if prompt_id not in hist:
            raise ComfyError(f"Histórico não tem o prompt {prompt_id}")
        entry = hist[prompt_id]
        outputs = entry.get("outputs", {})

        images = []
        filenames = []
        for node_id, node_out in outputs.items():
            if "images" in node_out:
                for img_meta in node_out["images"]:
                    data = self._download_image(
                        img_meta["filename"],
                        img_meta.get("subfolder", ""),
                        img_meta.get("type", "output"),
                    )
                    images.append(data)
                    filenames.append(img_meta["filename"])

        return GenerationResult(
            prompt_id=prompt_id,
            images=images,
            image_filenames=filenames,
            node_outputs=outputs,
        )

    def _download_image(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        params = urllib.parse.urlencode({
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type,
        })
        url = f"http://{self.server}/view?{params}"
        with urllib.request.urlopen(url, timeout=30.0) as resp:
            return resp.read()

    # --- ergonomia: salvar diretamente --------------------------------------

    def execute_and_save(self, workflow: dict, target_path: Path) -> Path:
        """Conveniência: executa e salva o primeiro PNG resultante em target_path."""
        result = self.execute(workflow)
        if not result.images:
            raise ComfyError("Workflow executou mas não produziu imagens.")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(result.images[0])
        return target_path


# ============================================================================
# Helper de degradação para OOM
# ============================================================================

def execute_with_oom_fallback(
    client: ComfyClient,
    workflow: dict,
    width: int = 1024,
    height: int = 1024,
    *,
    min_resolution: int = 512,
) -> GenerationResult:
    """
    Tenta executar; em OOM, reduz resolução pela metade e tenta de novo.
    """
    current_w, current_h = width, height
    attempt = 0
    while True:
        attempt += 1
        try:
            return client.execute(workflow)
        except ComfyOOMError:
            if current_w <= min_resolution:
                raise
            new_w = max(min_resolution, current_w // 2)
            new_h = max(min_resolution, current_h // 2)
            print(
                f"OOM detectado. Reduzindo {current_w}x{current_h} -> {new_w}x{new_h} (tentativa {attempt+1})"
            )
            # Substitui width/height em todos os nós que tenham
            for node in workflow.values():
                ins = node.get("inputs", {})
                if "width" in ins and isinstance(ins["width"], int):
                    ins["width"] = new_w
                if "height" in ins and isinstance(ins["height"], int):
                    ins["height"] = new_h
            current_w, current_h = new_w, new_h
            time.sleep(2.0)
