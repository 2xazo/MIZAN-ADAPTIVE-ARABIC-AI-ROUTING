"""Minimal OpenAI Chat Completions client over plain HTTPS.

No SDK on purpose: every parameter sent is explicit and logged, and the raw JSON response
is cached to disk so all analysis can be re-run offline without new API calls.
The API key is read from the environment and never logged.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.openai.com/v1"


class ApiError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:500]}")
        self.status = status
        self.body = body


def _key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set. Put it in the project's .env file.")
    return key


def _request(method: str, path: str, payload: dict | None, timeout: float) -> dict:
    req = urllib.request.Request(
        API_URL + path, method=method,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ApiError(e.code, e.read().decode("utf-8", "replace")) from None


def list_models(timeout: float = 30) -> list[dict]:
    return _request("GET", "/models", None, timeout).get("data", [])


def build_payload(model: str, messages: list[dict], call_cfg: dict, overrides: dict | None = None) -> dict:
    """Default payload; `overrides` lets the probe swap param names (e.g. max_completion_tokens)
    or drop params a model rejects. Structured outputs are never sent."""
    p = {
        "model": model,
        "messages": messages,
        "temperature": call_cfg["temperature"],
        "logprobs": call_cfg["logprobs"],
        "top_logprobs": call_cfg["top_logprobs"],
        "max_tokens": call_cfg["max_output_tokens"],
    }
    for k, v in (overrides or {}).items():
        if v is None:
            p.pop(k, None)
        else:
            p[k] = v
    if "max_completion_tokens" in p:
        p.pop("max_tokens", None)
    return p


def chat(payload: dict, timeout: float = 60, max_retries: int = 4) -> tuple[dict, float]:
    """POST /chat/completions with backoff on 429/5xx. Returns (response_json, latency_s)."""
    delay = 2.0
    for attempt in range(max_retries + 1):
        t0 = time.perf_counter()
        try:
            resp = _request("POST", "/chat/completions", payload, timeout)
            return resp, time.perf_counter() - t0
        except ApiError as e:
            if e.status in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError("unreachable")


def cache_path(cache_dir: Path, model: str, item_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in item_id)
    return Path(cache_dir) / model / f"{safe}.json"


def extract(resp: dict) -> dict:
    """Pull content, token logprobs and usage out of a raw response."""
    choice = resp["choices"][0]
    usage = resp.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    lp = (choice.get("logprobs") or {}).get("content")
    return {
        "content": choice["message"].get("content"),
        "finish_reason": choice.get("finish_reason"),
        "token_logprobs": lp,
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "reasoning_tokens": details.get("reasoning_tokens", 0),
        "model_returned": resp.get("model"),
    }
