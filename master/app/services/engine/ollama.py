from app.services.engine.base import DeployRequest, EngineAdapter, LaunchConfig


class OllamaAdapter(EngineAdapter):
    """Ollama 适配器。

    Ollama 由常驻守护进程提供服务（默认 11434 端口），「部署」即拉取模型
    到本机并借助其 OpenAI 兼容接口对外暴露。模型名即 Ollama tag（如 qwen2.5:7b）。
    """

    name = "ollama"
    supported_parallelism = ["single"]
    supported_quantization = ["q4_0", "q4_1", "q5_0", "q5_1", "q8_0", "f16"]

    def build_launch_config(self, req: DeployRequest) -> LaunchConfig:
        tag = req.model_name or req.model_path
        command = ["ollama", "pull", tag]
        return LaunchConfig(
            command=command,
            env={},
            port=11434,
            health_check_path="/api/tags",
        )
