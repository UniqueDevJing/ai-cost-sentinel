"""透明代理转发器"""

from __future__ import annotations
import httpx
import json
import time
import uuid
import logging

from config import UPSTREAM_BASE_URL, UPSTREAM_API_KEY, UPSTREAM_TIMEOUT, calculate_cost
from tracker.db import log_call

logger = logging.getLogger(__name__)

ALLOWED_PREFIXES = ("chat", "completions", "embeddings", "models", "images", "moderations")


async def forward_request(
    method: str,
    path: str,
    headers: dict,
    body: bytes,
    query_params: str = "",
    project: str = "default",
) -> dict:
    request_id = str(uuid.uuid4())[:8]
    start = time.time()

    url = f"{UPSTREAM_BASE_URL}{path}"
    if query_params:
        url += f"?{query_params}"

    fwd_headers = {
        k: v for k, v in headers.items()
        if k.lower() not in ("host", "authorization", "content-length")
    }
    if UPSTREAM_API_KEY:
        fwd_headers["authorization"] = f"Bearer {UPSTREAM_API_KEY}"

    model = _get_model(body)
    is_stream = _is_stream(body)

    try:
        async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT) as client:
            if is_stream:
                result = await _forward_stream(client, method, url, fwd_headers, body)
            else:
                result = await _forward_normal(client, method, url, fwd_headers, body)
    except Exception as e:
        logger.error(f"转发失败: {e}")
        return {
            "status_code": 502,
            "headers": {},
            "body": json.dumps({"error": str(e)}).encode(),
            "is_stream": is_stream,
            "model": model,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": str(e),
        }

    latency = int((time.time() - start) * 1000)
    cost_usd = calculate_cost(
        result.get("model") or model or "default",
        result.get("input_tokens", 0),
        result.get("output_tokens", 0),
    )

    await log_call(
        model=result.get("model") or model or "unknown",
        endpoint=path,
        input_tokens=result.get("input_tokens", 0),
        output_tokens=result.get("output_tokens", 0),
        cost_usd=cost_usd,
        latency_ms=latency,
        status_code=result["status_code"],
        project=project,
        request_id=request_id,
        error_msg=result.get("error", ""),
    )

    result["cost_usd"] = cost_usd
    result["request_id"] = request_id
    result["latency_ms"] = latency
    return result


async def _forward_normal(client, method, url, headers, body):
    resp = await client.request(method, url, headers=headers, content=body)
    resp_body = resp.content
    input_t = output_t = 0
    model = ""
    if resp.status_code == 200 and resp_body:
        try:
            data = json.loads(resp_body)
            model = data.get("model", "")
            usage = data.get("usage", {})
            input_t = usage.get("prompt_tokens", 0)
            output_t = usage.get("completion_tokens", 0)
        except json.JSONDecodeError:
            pass
    return {
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "body": resp_body,
        "is_stream": False,
        "model": model,
        "input_tokens": input_t,
        "output_tokens": output_t,
        "error": "" if resp.status_code < 400 else f"HTTP {resp.status_code}",
    }


async def _forward_stream(client, method, url, headers, body):
    chunks = []
    input_t = output_t = 0
    model = ""
    status_code = 200
    resp_headers = {}

    async with client.stream(method, url, headers=headers, content=body) as resp:
        status_code = resp.status_code
        resp_headers = dict(resp.headers)
        async for chunk in resp.aiter_bytes():
            chunks.append(chunk)
            if b'"usage"' in chunk:
                try:
                    text = chunk.decode("utf-8", errors="ignore")
                    for line in text.split("\n"):
                        if line.startswith("data: ") and line != "data: [DONE]":
                            data = json.loads(line[6:])
                            usage = data.get("usage", {})
                            if usage:
                                input_t = usage.get("prompt_tokens", 0)
                                output_t = usage.get("completion_tokens", 0)
                            if not model:
                                model = data.get("model", "")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass

    return {
        "status_code": status_code,
        "headers": resp_headers,
        "body": b"".join(chunks),
        "is_stream": True,
        "model": model,
        "input_tokens": input_t,
        "output_tokens": output_t,
        "error": "",
    }


def _get_model(body: bytes) -> str:
    try:
        return json.loads(body).get("model", "")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ""


def _is_stream(body: bytes) -> bool:
    try:
        return json.loads(body).get("stream", False) is True
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
