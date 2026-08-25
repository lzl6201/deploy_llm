import os
import subprocess

from config import settings

_BIN_TOKEN = "{LLAMA_CPP_BIN}"


def resolve_command(command: list[str]) -> list[str]:
    """解析 `{LLAMA_CPP_BIN}` 占位符，替换为 Agent 本机的 llama.cpp 二进制路径。"""
    exe = ".exe" if os.name == "nt" else ""
    resolved = []
    for tok in command:
        if tok.startswith(_BIN_TOKEN):
            name = tok[len(_BIN_TOKEN):]
            if settings.llama_cpp_bin_dir:
                resolved.append(os.path.join(settings.llama_cpp_bin_dir, name + exe))
            else:
                resolved.append(name + exe)
        else:
            resolved.append(tok)
    return resolved


class EngineRunner:
    """管理本机引擎进程（P0 裸金属模式，subprocess 启动）。

    P1 阶段扩展 Docker 模式：launch_config.container_image 非空时改用容器编排。
    """

    def __init__(self) -> None:
        self._processes: dict[int, subprocess.Popen] = {}

    def launch(
        self, deployment_id: int, command: list[str], env: dict[str, str]
    ) -> subprocess.Popen:
        merged = os.environ.copy()
        merged.update(env or {})
        proc = subprocess.Popen(
            resolve_command(command),
            env=merged,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self._processes[deployment_id] = proc
        return proc

    def stop(self, deployment_id: int) -> None:
        proc = self._processes.pop(deployment_id, None)
        if proc is not None and proc.poll() is None:
            proc.terminate()

    def is_running(self, deployment_id: int) -> bool:
        proc = self._processes.get(deployment_id)
        return proc is not None and proc.poll() is None
