from app.services.engine.base import DeployRequest, EngineAdapter, LaunchConfig
from app.services.engine.vllm import VllmAdapter
from app.services.engine.llama_cpp import LlamaCppAdapter
from app.services.engine.ollama import OllamaAdapter

ENGINES: dict[str, EngineAdapter] = {
    VllmAdapter.name: VllmAdapter(),
    LlamaCppAdapter.name: LlamaCppAdapter(),
    OllamaAdapter.name: OllamaAdapter(),
}


def get_engine(name: str) -> EngineAdapter:
    if name not in ENGINES:
        raise KeyError(f"engine '{name}' not registered")
    return ENGINES[name]


def list_engines() -> list[dict]:
    return [adapter.describe() for adapter in ENGINES.values()]


__all__ = [
    "DeployRequest",
    "EngineAdapter",
    "LaunchConfig",
    "ENGINES",
    "get_engine",
    "list_engines",
]
