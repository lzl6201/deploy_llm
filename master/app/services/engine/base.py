from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeployRequest:
    model_path: str
    model_name: str
    quantization: str = "none"
    gpu_ids: list[int] = field(default_factory=list)
    tp_size: int = 1
    pp_size: int = 1
    max_model_len: int = 4096
    port: int = 8000
    extra: dict = field(default_factory=dict)
    container_image: str = ""  # 非空则 Agent 走 Docker 编排


@dataclass
class LaunchConfig:
    command: list[str]
    env: dict[str, str]
    port: int = 8000
    health_check_path: str = "/health"
    # 预留 Docker 模式：非空则 Agent 用容器启动，否则裸金属 subprocess 启动
    container_image: Optional[str] = None


class EngineAdapter(ABC):
    name: str = "base"
    supported_parallelism: list[str] = []
    supported_quantization: list[str] = []

    @abstractmethod
    def build_launch_config(self, req: DeployRequest) -> LaunchConfig:
        """根据部署请求生成引擎启动命令与环境变量。"""

    def describe(self) -> dict:
        return {
            "name": self.name,
            "parallelism": self.supported_parallelism,
            "quantization": self.supported_quantization,
        }
