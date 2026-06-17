"""
透明代理转发器 — 转发请求到上游 API，提取 Token 用量

支持：
- 普通 JSON 请求/响应 (chat, embeddings, etc.)
- 流式响应 (SSE) — 从 stream 中累加 token 计数
- 透传所有请求头和响应头
"""

from __future__ import annotations

import httpx
import json
import time
import uuid

from config import (
    UPSTREAM_BASE_URL,
    UPSTREAM_API_KEY,
    UPSTREAM_TIMEOUT,
    calculate_cost,
)
from tracker.db import log_call


async def forward_request(
    method: str,
    path: str,
    headers: dict,
    body: bytes,
    query_params: str = "",
    project: str = "default",
) -> dict:
    """
    转发请求到上游 API，返回响应数据 + Token 统计

    Returns:
        {
            "status_code": int,
            "headers": dict,
            "body": bytes,          # 响应体
            "is_stream": bool,
            "model": str,           # 从请求体中提取
            "input_tokens": int,
            "output_tokens": int,
            "cost_usd": float,
        }
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # 构建上游 URL
    target_url = f"{UPSTREAM_BASE_URL}{path}"
    if query_params:
        target_url += f"?{query_params}"

    # 准备转发请求头（替换 API Key）
    forward_headers = {k: v for k, v in headers.items()
                       if k.lower() not in ("host", "authorization", "content-length")}
    if UPSTREAM_API_KEY:
        forward_headers["authorization"] = f"Bearer {UPSTREAM_API_KEY}"

    # 从请求体中提取 model
    model = _extract_model(body)
    is_stream = _is_stream_request(body)

    # 转发
    async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT) as client:
        if is_stream:
            result = await _forward_stream(
                client, method, target_url, forward_headers, body
            )
        else:
            result = await _forward_normal(
                client, method, target_url, forward_headers, body
            )

    latency_ms = int((time.time() - start_time) * 1000)

    # 计算费用
    cost = calculate_cost(
        result["model"] or model or "default",
        result["input_tokens"],
        result["output_tokens"],
    )

    # 异步记录
    await log_call(
        model=result["model"] or model or "unknown",
        endpoint=path,
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        cost_usd=cost,
        latency_ms=latency_ms,
        status_code=result["status_code"],
        project=project,
        request_id=request_id,
        error_msg=result.get("error", ""),
    )

    result["cost_usd"] = cost
    result["request_id"] = request_id
    result["latency_ms"] = latency_ms
    return result


async def _forward_normal(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict,
    body: bytes,
) -> dict:
    """转发普通 JSON 请求"""
    try:
        resp = await client.request(
            method, url, headers=headers, content=body
        )
        resp_body = resp.content
        input_tokens = 0
        output_tokens = 0
        model = ""

        if resp.status_code == 200 and resp_body:
            try:
                data = json.loads(resp_body)
                model = data.get("model", "")
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
            except json.JSONDecodeError:
                pass

        return {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp_body,
            "is_stream": False,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "error": "" if resp.status_code < 400 else f"HTTP {resp.status_code}",
        }
    except Exception as e:
        return {
            "status_code": 502,
            "headers": {},
            "body": json.dumps({"error": str(e)}).encode(),
            "is_stream": False,
            "model": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "error": str(e),
        }


async def _forward_stream(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict,
    body: bytes,
) -> dict:
    """转发流式 (SSE) 请求 — 累加 token 计数"""
    chunks: list[bytes] = []
    input_tokens = 0
    output_tokens = 0
    model = ""
    status_code = 200
    error = ""

    try:
        async with client.stream(method, url, headers=headers, content=body) as resp:
            status_code = resp.status_code
            async for chunk in resp.aiter_bytes():
                chunks.append(chunk)
                # 从 SSE chunk 中提取 usage（通常在最后一个 chunk）
                if b'"usage"' in chunk:
                    try:
                        text = chunk.decode("utf-8", errors="ignore")
                        for line in text.split("\n"):
                            if line.startswith("data: ") and line != "data: [DONE]":
                                data = json.loads(line[6:])
                                usage = data.get("usage", {})
                                if usage:
                                    input_tokens = usage.get("prompt_tokens", 0)
                                    output_tokens = usage.get("completion_tokens", 0)
                                if not model:
                                    model = data.get("model", "")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass

        full_body = b"".join(chunks)
        return {
            "status_code": status_code,
            "headers": dict(resp.headers) if 'resp' in dir() else {},
            "body": full_body,
            "is_stream": True,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "error": error,
        }
    except Exception as e:
        return {
            "status_code": 502,
            "headers": {},
            "body": json.dumps({"error": str(e)}).encode(),
            "is_stream": True,
            "model": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "error": str(e),
        }


def _extract_model(body: bytes) -> str:
    """从请求体中提取模型名称"""
    try:
        data = json.loads(body)
        return data.get("model", "")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ""


def _is_stream_request(body: bytes) -> bool:
    """判断是否为流式请求"""
    try:
        data = json.loads(body)
        return data.get("stream", False) is True
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
