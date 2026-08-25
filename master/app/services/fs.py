"""安全文件系统浏览。

仅允许访问 `settings.allowed_fs_roots` 白名单内的路径，用于模型仓库的
「选择模型文件/目录」交互。所有路径先 `os.path.realpath` 归一化，再校验
是否落在某个白名单根目录内，防止目录穿越。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.config import settings


class FSPermissionError(Exception):
    """请求的路径不在白名单内。"""


@dataclass
class FSEntry:
    name: str
    path: str
    type: str  # dir / file
    size_bytes: int = 0
    is_gguf: bool = False


def _resolve(path: str) -> str:
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def _within_roots(path: str) -> bool:
    resolved = _resolve(path)
    for root in settings.allowed_fs_roots:
        root_resolved = _resolve(root)
        if resolved == root_resolved or resolved.startswith(root_resolved + os.sep):
            return True
    return False


def _assert_allowed(path: str) -> str:
    resolved = _resolve(path)
    if not _within_roots(resolved):
        raise FSPermissionError(
            f"路径不在允许范围内: {path}（白名单: {', '.join(settings.allowed_fs_roots)}）"
        )
    return resolved


def list_dir(path: str) -> tuple[str, list[FSEntry]]:
    """列出目录，返回 (当前目录, 条目列表)。目录在前，GGUF/文件在后。"""
    resolved = _assert_allowed(path)
    if not os.path.isdir(resolved):
        raise FSPermissionError(f"不是目录: {path}")

    dirs: list[FSEntry] = []
    files: list[FSEntry] = []
    try:
        names = sorted(os.listdir(resolved))
    except OSError as exc:
        raise FSPermissionError(f"无法读取目录: {exc}") from exc

    for name in names:
        full = os.path.join(resolved, name)
        try:
            if os.path.isdir(full):
                dirs.append(FSEntry(name=name, path=full, type="dir"))
            elif os.path.isfile(full):
                is_gguf = name.lower().endswith(".gguf")
                size = os.path.getsize(full)
                files.append(
                    FSEntry(
                        name=name,
                        path=full,
                        type="file",
                        size_bytes=size,
                        is_gguf=is_gguf,
                    )
                )
        except OSError:
            continue

    # 模型目录通常以子目录为主，其次展示可直接导入的 GGUF 文件
    return resolved, dirs + files


def list_roots() -> list[dict]:
    """返回白名单根目录（供前端展示起始位置）。"""
    return [
        {"path": _resolve(r), "exists": os.path.isdir(_resolve(r))}
        for r in settings.allowed_fs_roots
    ]


def parent_of(path: str) -> str:
    resolved = _assert_allowed(path)
    parent = os.path.dirname(resolved)
    # 退回白名单内才允许；若已到根之上则停在根
    if not _within_roots(parent):
        return resolved
    return parent
