import os
from dataclasses import dataclass, field


def _list_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [p.strip() for p in raw.split(",") if p.strip()]


@dataclass
class Settings:
    app_name: str = "LLM Deploy Platform"
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./deploy_llm.db")
    )
    # Master 校验 Agent 注册/心跳用的共享密钥；后续升级为签发式 token
    agent_auth_token: str = field(
        default_factory=lambda: os.getenv("AGENT_AUTH_TOKEN", "change-me-agent-token")
    )
    # 模型共享存储挂载点（NFS/S3）。生产环境所有节点同一路径挂载。
    model_storage_base: str = field(
        default_factory=lambda: os.getenv("MODEL_STORAGE_BASE", "/mnt/models")
    )
    # 文件浏览白名单根目录（逗号分隔）。默认仅允许 model_storage_base。
    allowed_fs_roots: list[str] = field(
        default_factory=lambda: _list_env(
            "ALLOWED_FS_ROOTS", os.getenv("MODEL_STORAGE_BASE", "/mnt/models")
        )
    )
    engine_default: str = field(
        default_factory=lambda: os.getenv("ENGINE_DEFAULT", "vllm")
    )
    # llama.cpp 可执行文件目录（llama-server / llama-quantize），Agent 本机路径
    llama_cpp_bin_dir: str = field(
        default_factory=lambda: os.getenv("LLAMA_CPP_BIN_DIR", "")
    )
    # Ollama 服务地址（仅用于 Ollama 引擎适配）
    ollama_host: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    )
    # HuggingFace Hub 镜像端点（国内默认走 hf-mirror.com）
    hf_endpoint: str = field(
        default_factory=lambda: os.getenv("HF_ENDPOINT", "https://hf-mirror.com")
    )
    # 可选：访问 gated/私有模型用的 HF token
    hf_token: str = field(default_factory=lambda: os.getenv("HF_TOKEN", ""))
    # HF 模型下载落盘目录（默认与共享模型存储一致）
    hf_download_dir: str = field(
        default_factory=lambda: os.getenv(
            "HF_DOWNLOAD_DIR", os.getenv("MODEL_STORAGE_BASE", "/mnt/models")
        )
    )


settings = Settings()
