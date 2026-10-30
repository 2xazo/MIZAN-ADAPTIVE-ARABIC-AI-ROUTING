import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def tok(token, p, alts=None):
    """Build one Chat Completions logprob entry. alts: {token: prob}."""
    return {"token": token, "logprob": math.log(p), "bytes": list(token.encode()),
            "top_logprobs": [{"token": t, "logprob": math.log(q)} for t, q in (alts or {token: p}).items()]}


def fake_response(content, token_entries, prompt_tokens=100, completion_tokens=1, model="m"):
    return {"model": model,
            "choices": [{"message": {"content": content}, "finish_reason": "stop",
                         "logprobs": {"content": token_entries}}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}}
