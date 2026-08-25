"""GGUF 模型元数据解析器。

依赖 `gguf` 官方包读取 .gguf 文件的元数据（架构、参数量、上下文长度、
量化档位等），供模型仓库导入、自动推荐与量化任务使用。

设计约束：
- 解析失败时抛 :class:`GGUFError`，由上层捕获后降级为「手工填写」。
- 参数量采用多级回退：general.parameter_count -> 名称中的 "XB" -> 维度公式 ->
  文件大小估算，保证不同来源的 GGUF 都能得到一个可用的估值。
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Optional

try:
    from gguf import GGUFReader
    from gguf.constants import LlamaFileType

    HAS_GGUF = True
except Exception:  # pragma: no cover - gguf 未安装时降级
    HAS_GGUF = False

# GGUF 解析结果缓存（模型文件不可变，以路径 + mtime + 大小作键）。
# 大模型（数十 GB）每次解析约需数秒，推荐/调度高频调用需缓存避免重复读取。
_CACHE_TTL = 300
_parse_cache: dict[str, tuple[float, GGUFinfo]] = {}


class GGUFError(Exception):
    """GGUF 解析失败（非 GGUF 文件、损坏、依赖缺失等）。"""


@dataclass
class GGUFinfo:
    path: str
    file_size_bytes: int
    architecture: str = ""
    name: str = ""
    file_type: int = 0
    file_type_label: str = ""
    params_b: float = 0.0
    params_source: str = ""
    context_len: int = 0
    block_count: int = 0
    embedding_length: int = 0
    feed_forward_length: int = 0
    head_count: int = 0
    head_count_kv: int = 0
    key_length: int = 0
    vocab_size: int = 0
    tensor_count: int = 0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "file_size_bytes": self.file_size_bytes,
            "file_size_gb": round(self.file_size_bytes / (1024**3), 3),
            "architecture": self.architecture,
            "name": self.name,
            "file_type": self.file_type,
            "file_type_label": self.file_type_label,
            "params_b": round(self.params_b, 2),
            "params_source": self.params_source,
            "context_len": self.context_len,
            "block_count": self.block_count,
            "embedding_length": self.embedding_length,
            "feed_forward_length": self.feed_forward_length,
            "head_count": self.head_count,
            "head_count_kv": self.head_count_kv,
            "key_length": self.key_length,
            "vocab_size": self.vocab_size,
            "tensor_count": self.tensor_count,
        }


# file_type -> 每参数近似 bit 数（用于文件大小回退估算参数量）
_BITS_PER_WEIGHT: dict[int, float] = {
    0: 32.0,
    1: 16.0,
    2: 4.5,
    3: 5.0,
    6: 5.5,
    7: 6.0,
    8: 8.5,
    10: 2.5625,
    11: 3.4375,
    12: 3.6875,
    13: 3.875,
    14: 4.5,
    15: 4.75,
    16: 5.5,
    17: 5.75,
    18: 6.5625,
}

_NAME_PARAMS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[bB]")


def _file_type_label(file_type: int) -> str:
    """返回人类可读的量化档位（如 Q3_K_L / F16）。"""
    try:
        name = LlamaFileType(file_type).name
        return name.removeprefix("MOSTLY_")
    except Exception:
        return _UNKNOWN_FILE_TYPE.get(file_type, f"type{file_type}")


_UNKNOWN_FILE_TYPE: dict[int, str] = {}


def _value(reader: GGUFReader, key: str, default=None):
    field = reader.fields.get(key)
    if field is None:
        return default
    try:
        return field.contents()
    except Exception:
        return default


def _parse_params_from_name(name: str) -> Optional[float]:
    m = _NAME_PARAMS_RE.search(name or "")
    return float(m.group(1)) if m else None


def _estimate_params_from_dims(meta: dict) -> float:
    """按 LLaMA/Qwen 类 decoder-only 结构估算参数量（含嵌入与输出）。"""
    v = meta.get("vocab_size") or 0
    h = meta.get("embedding_length") or 0
    f = meta.get("feed_forward_length") or 0
    l = meta.get("block_count") or 0
    n_kv = meta.get("head_count_kv") or 0
    if not (v and h and f and l):
        return 0.0

    n_head = meta.get("head_count") or 0
    head_dim = h // n_head if n_head else h
    kv_dim = (n_kv * head_dim) if n_kv else h

    embedding = v * h
    per_layer = (
        h * h            # q_proj
        + h * kv_dim     # k_proj
        + h * kv_dim     # v_proj
        + h * h          # o_proj
        + 3 * h * f      # gate + up + down
    )
    total = embedding + l * per_layer + v * h  # 嵌入 + 层 + 输出头（保守按不共享计）
    return total / 1e9


def _estimate_params_from_size(file_size_bytes: int, file_type: int) -> float:
    bits = _BITS_PER_WEIGHT.get(file_type)
    if not bits:
        return 0.0
    # GGUF 文件几乎全为权重，去掉少量元数据/tokenizer 开销后换算参数量
    weight_bytes = file_size_bytes * 0.98
    return (weight_bytes * 8 / bits) / 1e9


def _cache_key(path: str) -> str | None:
    try:
        st = os.stat(path)
        return f"{os.path.abspath(path)}:{st.st_mtime_ns}:{st.st_size}"
    except OSError:
        return None


def parse_gguf(path: str) -> GGUFinfo:
    """解析单个 .gguf 文件，返回 :class:`GGUFinfo`（带进程内缓存）。"""
    if not HAS_GGUF:
        raise GGUFError("gguf 包未安装，无法解析 GGUF 元数据")
    if not os.path.isfile(path):
        raise GGUFError(f"文件不存在: {path}")

    key = _cache_key(path)
    if key is not None:
        hit = _parse_cache.get(key)
        if hit is not None and time.time() - hit[0] < _CACHE_TTL:
            return hit[1]

    try:
        reader = GGUFReader(path)
    except Exception as exc:  # 非 GGUF / 损坏文件
        raise GGUFError(f"无法解析 GGUF 文件: {exc}") from exc

    arch = _value(reader, "general.architecture", "") or ""
    name = _value(reader, "general.name", "") or os.path.basename(path)
    file_type = int(_value(reader, "general.file_type", 0) or 0)

    head_count = int(
        _value(reader, f"{arch}.attention.head_count", None)
        or _value(reader, f"{arch}.head_count", 0)
        or 0
    )
    head_count_kv = int(
        _value(reader, f"{arch}.attention.head_count_kv", None)
        or _value(reader, f"{arch}.head_count_kv", 0)
        or 0
    )
    key_length = int(
        _value(reader, f"{arch}.attention.key_length", None)
        or _value(reader, f"{arch}.attention.value_length", 0)
        or 0
    )

    meta = {
        "vocab_size": _vocab_size(reader),
        "embedding_length": int(_value(reader, f"{arch}.embedding_length", 0) or 0),
        "feed_forward_length": int(_value(reader, f"{arch}.feed_forward_length", 0) or 0),
        "block_count": int(_value(reader, f"{arch}.block_count", 0) or 0),
        "head_count": head_count,
        "head_count_kv": head_count_kv,
    }

    file_size_bytes = os.path.getsize(path)
    params_b, params_source = _resolve_params(reader, name, file_type, meta, file_size_bytes)

    info = GGUFinfo(
        path=os.path.abspath(path),
        file_size_bytes=file_size_bytes,
        architecture=arch,
        name=name,
        file_type=file_type,
        file_type_label=_file_type_label(file_type),
        params_b=params_b,
        params_source=params_source,
        context_len=int(_value(reader, f"{arch}.context_length", 0) or 0),
        block_count=meta["block_count"],
        embedding_length=meta["embedding_length"],
        feed_forward_length=meta["feed_forward_length"],
        head_count=meta["head_count"],
        head_count_kv=meta["head_count_kv"],
        key_length=key_length,
        vocab_size=meta["vocab_size"],
        tensor_count=len(reader.tensors),
    )
    if key is not None:
        _parse_cache[key] = (time.time(), info)
    return info


def _vocab_size(reader: GGUFReader) -> int:
    try:
        field = reader.fields.get("tokenizer.ggml.tokens")
        if field is None:
            return 0
        return len(field.contents())
    except Exception:
        return 0


def _resolve_params(
    reader: GGUFReader, name: str, file_type: int, meta: dict, file_size_bytes: int
) -> tuple[float, str]:
    declared = _value(reader, "general.parameter_count", None)
    if declared:
        return float(declared) / 1e9, "metadata"

    from_name = _parse_params_from_name(name)
    if from_name:
        return from_name, "name"

    from_dims = _estimate_params_from_dims(meta)
    if from_dims > 0:
        return from_dims, "dims"

    from_size = _estimate_params_from_size(file_size_bytes, file_type)
    if from_size > 0:
        return from_size, "size"

    return 0.0, "unknown"
