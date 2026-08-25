from app.services.engine.base import DeployRequest, EngineAdapter, LaunchConfig


class VllmAdapter(EngineAdapter):
    name = "vllm"
    supported_parallelism = ["tp", "pp", "multi_node"]
    supported_quantization = ["none", "fp8", "awq", "gptq", "squeezellm"]

    def build_launch_config(self, req: DeployRequest) -> LaunchConfig:
        command = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--model", req.model_path,
            "--served-model-name", req.model_name,
            "--tensor-parallel-size", str(req.tp_size),
            "--pipeline-parallel-size", str(req.pp_size),
            "--max-model-len", str(req.max_model_len),
            "--port", str(req.port),
        ]
        if req.quantization and req.quantization != "none":
            command += ["--quantization", req.quantization]

        env = {}
        # 跨机张量并行：extra 提供 Ray 地址时启用 worker-use-ray（P3，需 IB/RDMA）
        ray_address = (req.extra or {}).get("ray_address")
        if ray_address:
            command += ["--worker-use-ray"]
            env["RAY_ADDRESS"] = ray_address

        if req.gpu_ids:
            # vLLM 通过 CUDA_VISIBLE_DEVICES 约束可见 GPU
            env["CUDA_VISIBLE_DEVICES"] = ",".join(str(g) for g in req.gpu_ids)

        return LaunchConfig(
            command=command,
            env=env,
            port=req.port,
            container_image=req.container_image or None,
        )
