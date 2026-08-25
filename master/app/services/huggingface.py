"""HuggingFace Hub 模型发现与下载（走国内镜像 hf-mirror.com）。

通过 HF Hub 的 JSON API（`/api/models`）搜索/浏览模型，而非抓取 HTML。
Master 直连镜像（`trust_env=False`），绕过本机系统代理，避免误走
`127.0.0.1:7890` 之类的失效代理。搜索结果做 5 分钟内存 TTL 缓存。
"""

from __future__ import annotations

import time
import urllib.parse

import httpx

from app.config import settings

GGUF_ORGS = ["bartowski", "TheBloke", "ggml-org", "lmstudio-community"]

_CACHE_TTL = 300  # 秒


class HFError(Exception):
    """HuggingFace Hub 请求失败（网络 / 404 / 超时）。"""


def _headers() -> dict[str, str]:
    if settings.hf_token:
        return {"Authorization": f"Bearer {settings.hf_token}"}
    return {}


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.hf_endpoint, timeout=30.0, trust_env=False)


# 简单内存 TTL 缓存：key -> (expire_ts, value)
_cache: dict[str, tuple[float, list[dict]]] = {}


def _cached(key: str, fetcher):
    now = time.time()
    hit = _cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    value = fetcher()
    _cache[key] = (now + _CACHE_TTL, value)
    return value


def _card(m: dict) -> dict:
    return {
        "id": m.get("id") or m.get("modelId") or "",
        "downloads": m.get("downloads", 0),
        "likes": m.get("likes", 0),
        "tags": m.get("tags") or [],
        "pipeline_tag": m.get("pipeline_tag", ""),
        "created_at": m.get("createdAt", ""),
    }


def search_models(query: str, limit: int = 20, sort: str = "downloads") -> list[dict]:
    """按关键词搜索模型，按下载量/点赞排序。"""
    if not query.strip():
        return []

    def fetch():
        params = {
            "search": query.strip(),
            "limit": max(1, min(limit, 100)),
            "sort": sort or "downloads",
            "direction": "-1",
            "full": "true",
        }
        with _client() as c:
            resp = c.get("/api/models", params=params, headers=_headers())
        if resp.status_code == 404:
            return []
        if resp.is_error:
            raise HFError(f"HF 搜索失败: HTTP {resp.status_code}")
        return [_card(m) for m in resp.json() if m.get("id")]

    key = f"search:{query.strip().lower()}:{limit}:{sort}"
    return _cached(key, fetch)


def list_org_models(org: str, limit: int = 20) -> list[dict]:
    """列出某组织（如 bartowski）的模型，按下载量排序。"""
    if not org.strip():
        return []

    def fetch():
        params = {
            "author": org.strip(),
            "limit": max(1, min(limit, 100)),
            "sort": "downloads",
            "direction": "-1",
            "full": "true",
        }
        with _client() as c:
            resp = c.get("/api/models", params=params, headers=_headers())
        if resp.status_code == 404:
            return []
        if resp.is_error:
            raise HFError(f"HF 组织查询失败: HTTP {resp.status_code}")
        return [_card(m) for m in resp.json() if m.get("id")]

    key = f"org:{org.strip().lower()}:{limit}"
    return _cached(key, fetch)


def get_model_files(repo_id: str) -> list[dict]:
    """列出仓库根目录文件，标记 GGUF 与大小。"""
    repo = repo_id.strip("/")
    with _client() as c:
        resp = c.get(f"/api/models/{repo}/tree/main", headers=_headers())
    if resp.status_code == 404:
        raise HFError(f"模型不存在: {repo_id}")
    if resp.is_error:
        raise HFError(f"HF 文件列表失败: HTTP {resp.status_code}")

    files = []
    for item in resp.json():
        if item.get("type") != "file":
            continue
        path = item.get("path", "")
        files.append(
            {
                "path": path,
                "size": item.get("size") or 0,
                "is_gguf": path.lower().endswith(".gguf"),
            }
        )
    files.sort(key=lambda f: (not f["is_gguf"], f["path"].lower()))
    return files


def resolve_url(repo_id: str, filename: str) -> str:
    repo = repo_id.strip("/")
    name = urllib.parse.quote(filename.strip("/"), safe="")
    return f"{settings.hf_endpoint}/{repo}/resolve/main/{name}"


def download_to_file(
    repo_id: str, filename: str, dest_path: str, progress_cb=None, expected_size: int = 0
) -> int:
    """流式下载文件到 dest_path（先写 .part，成功后 rename），返回字节数。

    progress_cb(downloaded_bytes, total_bytes) 在下载过程中被周期性调用。
    镜像直链可能不带 content-length（chunked），此时回退到 expected_size 计算进度。
    """
    url = resolve_url(repo_id, filename)
    part = dest_path + ".part"
    with _client() as c:
        with c.stream("GET", url, headers=_headers(), follow_redirects=True) as resp:
            if resp.status_code == 404:
                raise HFError(f"文件不存在: {filename}")
            if resp.is_error:
                raise HFError(f"HF 下载失败: HTTP {resp.status_code}")
            total = int(resp.headers.get("content-length") or 0) or expected_size
            downloaded = 0
            last_report_bytes = 0
            last_report_ts = 0.0
            with open(part, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if progress_cb and (
                        downloaded - last_report_bytes >= 5 * 1024 * 1024
                        or now - last_report_ts >= 2
                    ):
                        progress_cb(downloaded, total)
                        last_report_bytes = downloaded
                        last_report_ts = now
            if progress_cb:
                progress_cb(downloaded, total)
            return downloaded
