"""对外 OpenAI 兼容网关：/v1/chat/completions、/v1/completions、/v1/models。

按请求体中的 `model` 字段匹配运行实例并反向代理（支持 SSE 流式透传）。
"""

import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.gateway import GatewayError, mark_down, select_backend, served_models

router = APIRouter(tags=["gateway"])


def _extract_model(body: bytes) -> str:
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return ""
    return data.get("model", "") if isinstance(data, dict) else ""


async def _proxy(request: Request, db: Session, body: bytes, model: str):
    try:
        _, endpoint = select_backend(db, model)
    except GatewayError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    url = f"{endpoint.rstrip('/')}{request.url.path}"
    headers = {"Content-Type": request.headers.get("content-type", "application/json")}
    client = httpx.AsyncClient(timeout=None, trust_env=False)
    try:
        upstream = await client.send(
            client.build_request("POST", url, content=body, headers=headers),
            stream=True,
        )
    except httpx.HTTPError:
        await client.aclose()
        mark_down(endpoint)
        raise HTTPException(status_code=502, detail=f"上游 {endpoint} 不可达")

    content_type = upstream.headers.get("content-type", "application/json")
    media = "text/event-stream" if "text/event-stream" in content_type else "application/json"

    if upstream.status_code >= 400:
        content = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        return Response(content=content, status_code=upstream.status_code, media_type=media)

    async def gen():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(gen(), status_code=upstream.status_code, media_type=media)


@router.get("/v1/models")
def models(db: Session = Depends(get_db)):
    return {"object": "list", "data": served_models(db)}


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    model = _extract_model(body)
    if not model:
        raise HTTPException(status_code=400, detail="请求体缺少 'model' 字段")
    return await _proxy(request, db, body, model)


@router.post("/v1/completions")
async def completions(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    model = _extract_model(body)
    if not model:
        raise HTTPException(status_code=400, detail="请求体缺少 'model' 字段")
    return await _proxy(request, db, body, model)
