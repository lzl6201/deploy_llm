from app.services.engine.base import DeployRequest, EngineAdapter, LaunchConfig


class LlamaCppAdapter(EngineAdapter):
    """llama.cpp `llama-server`（OpenAI 兼容）适配器。

    直接加载 GGUF 文件，量化档位内嵌于 GGUF 文件中，无需额外量化参数。
    二进制路径由 Agent 侧解析（`{LLAMA_CPP_BIN}` 占位符），避免 Master 与
    节点二进制路径不一致的问题。
    """

    name = "llama.cpp"
    supported_parallelism = ["single", "tp"]  # llama.cpp 以单卡/单机为主
    supported_quantization = [
        "F16", "F32", "Q8_0", "Q6_K", "Q5_K_M", "Q5_K_S",
        "Q4_K_M", "Q4_K_S", "Q3_K_L", "Q3_K_M", "Q3_K_S", "Q2_K",
    ]

    def build_launch_config(self, req: DeployRequest) -> LaunchConfig:
        extra = req.extra or {}
        n_gpu_layers = int(extra.get("n_gpu_layers", 999))  # 默认全部层卸载到 GPU
        n_ctx = req.max_model_len or int(extra.get("n_ctx", 4096))
        n_parallel = int(extra.get("n_parallel", 1))

        command = [
            "{LLAMA_CPP_BIN}llama-server",
            "--model", req.model_path,
            "--host", "0.0.0.0",
            "--port", str(req.port),
            "--n-gpu-layers", str(n_gpu_layers),
            "--ctx-size", str(n_ctx),
            "--parallel", str(n_parallel),
        ]

        env: dict[str, str] = {}
        if req.gpu_ids:
            env["CUDA_VISIBLE_DEVICES"] = ",".join(str(g) for g in req.gpu_ids)

        return LaunchConfig(
            command=command,
            env=env,
            port=req.port,
            health_check_path="/health",
        )
