"""Live probe: which candidate models exist in THIS account and which params they accept.

    python scripts/probe_models.py

One tiny request per candidate (a few hundred tokens total). Writes artifacts/model_probe.json.
Never prints the API key.
"""
import _common  # noqa: F401
import json
import time

from mizan import client
from mizan.config import PROBE_FILE, experiment
from mizan.parsing import parse_response

PROBE_ITEM = {"question": "ما عاصمة المملكة العربية السعودية؟",
              "options": ["جدة", "الرياض", "مكة", "الدمام"], "context": ""}


def try_call(model, cfg, overrides):
    from mizan.prompts import build_messages
    payload = client.build_payload(model, build_messages(PROBE_ITEM, cfg["prompt"]["system"]),
                                   cfg["call"], overrides)
    resp, lat = client.chat(payload, cfg["call"]["timeout_s"], max_retries=1)
    return payload, resp, lat


def probe(model, cfg):
    """Try the agreed params, then adapt ONLY where the API says a param is unsupported."""
    attempts = [
        {},
        {"max_completion_tokens": cfg["call"]["max_output_tokens"]},
        {"max_completion_tokens": cfg["call"]["max_output_tokens"], "reasoning_effort": "none"},
        {"max_completion_tokens": cfg["call"]["max_output_tokens"], "reasoning_effort": "none",
         "temperature": None},
    ]
    errors = []
    for ov in attempts:
        try:
            payload, resp, lat = try_call(model, cfg, ov)
        except client.ApiError as e:
            errors.append({"overrides": ov, "status": e.status, "error": e.body[:300]})
            continue
        ex = client.extract(resp)
        parsed = parse_response(ex["content"], ex["token_logprobs"], "ABCD")
        lp = ex["token_logprobs"] or []
        return {
            "ok": True, "overrides": ov, "latency_s": lat,
            "model_returned": ex["model_returned"], "content": ex["content"],
            "finish_reason": ex["finish_reason"],
            "logprobs_returned": bool(lp),
            "top_logprobs_returned": max((len(t.get("top_logprobs") or []) for t in lp), default=0),
            "output_tokens_seen": [t["token"] for t in lp],
            "usage": {"input": ex["input_tokens"], "output": ex["output_tokens"],
                      "reasoning": ex["reasoning_tokens"]},
            "parsed_valid": parsed["valid"], "parsed_letter": parsed["letter"],
            "normalized_complete": parsed["normalized_complete"],
            "rejected_attempts": errors,
        }
    return {"ok": False, "rejected_attempts": errors}


def main():
    cfg = experiment()
    available = {m["id"]: m for m in client.list_models()}
    cands = list(dict.fromkeys(cfg["candidates"]["small"] + cfg["candidates"]["large"]))
    report = {"probed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "models": {}}
    for m in cands:
        meta = available.get(m)
        entry = {"listed_in_account": meta is not None,
                 "shutdown_date": (meta or {}).get("shutdown_date")}
        if meta is not None:
            entry.update(probe(m, cfg))
        report["models"][m] = entry
        print(f"{m:16s} listed={entry['listed_in_account']!s:5s} ok={entry.get('ok')!s:5s} "
              f"logprobs={entry.get('logprobs_returned')!s:5s} top={entry.get('top_logprobs_returned')} "
              f"answer={entry.get('content')!r}")
    PROBE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROBE_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"-> {PROBE_FILE}")


if __name__ == "__main__":
    main()
