"""GGUF 量化服务。

基于 llama.cpp `llama-quantize`，将 FP16/F32 的源 GGUF 量化为目标档位。
由 Agent 拉取待量化任务并在本机执行（二进制路径同样用 `{LLAMA_CPP_BIN}` 占位符）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# llama-quantize 支持的常见档位
GGUF_QUANT_TYPES = [
    "F16", "Q8_0", "Q6_K", "Q5_K_M", "Q5_K_S",
    "Q4_K_M", "Q4_K_S", "Q3_K_L", "Q3_K_M", "Q3_K_S", "Q2_K",
]


@dataclass
class QuantizeCommand:
    command: list[str]
    source_path: str
    target_path: str


def build_quantize_command(source_path: str, target_quant: str) -> QuantizeCommand:
    """生成 llama-quantize 命令，输出文件与源文件同目录，带量化档位后缀。"""
    directory = os.path.dirname(source_path)
    stem, ext = os.path.splitext(os.path.basename(source_path))
    target_name = f"{stem}-{target_quant}{ext}"
    target_path = os.path.join(directory, target_name)

    command = [
        "{LLAMA_CPP_BIN}llama-quantize",
        source_path,
        target_path,
        target_quant,
    ]
    return QuantizeCommand(command=command, source_path=source_path, target_path=target_path)
