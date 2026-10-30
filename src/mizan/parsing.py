"""Answer extraction and confidence signals from Chat Completions logprobs.

Rules (agreed with the coordinator):
- A response is VALID only if the whole content, stripped, is exactly one allowed letter.
  Anything else ("Answer: A", "A.", explanations) is invalid -> automatic escalation.
- The answer token is the first non-whitespace token, not the first token overall.
- Signals:
  * raw_logprob: provider logprob of the answer token (primary, always available when valid)
  * normalized: p(chosen) / sum p(valid letters), ONLY if every valid letter appears in
    top_logprobs at that position (after stripping whitespace and merging variants like ' A').
  * margin: logprob(chosen) - logprob(best other valid letter), or "not_available".
"""
from __future__ import annotations

import math

NOT_AVAILABLE = "not_available"


def clean(token: str) -> str:
    return token.strip()


def parse_response(content: str | None, token_logprobs: list[dict] | None, letters: str) -> dict:
    out = {
        "content": content,
        "valid": False,
        "letter": None,
        "invalid_reason": None,
        "answer_token": None,
        "answer_token_bytes": None,
        "skipped_whitespace_tokens": 0,
        "raw_logprob": None,
        "normalized": None,
        "normalized_complete": False,
        "margin": NOT_AVAILABLE,
    }
    text = clean(content or "")
    if len(text) != 1 or text not in letters:
        out["invalid_reason"] = "empty" if not text else "not_single_valid_letter"
        return out
    if not token_logprobs:
        out["invalid_reason"] = "no_logprobs"
        return out

    pos = None
    for i, t in enumerate(token_logprobs):
        if clean(t.get("token", "")):
            pos = i
            break
    if pos is None or clean(token_logprobs[pos]["token"]) != text:
        out["invalid_reason"] = "answer_token_mismatch"
        return out

    tok = token_logprobs[pos]
    out.update(valid=True, letter=text, answer_token=tok["token"],
               answer_token_bytes=tok.get("bytes"), skipped_whitespace_tokens=pos,
               raw_logprob=tok["logprob"])

    # Aggregate alternatives at the answer position by cleaned letter.
    probs: dict[str, float] = {}
    for alt in tok.get("top_logprobs") or []:
        c = clean(alt.get("token", ""))
        if c in letters and len(c) == 1:
            probs[c] = probs.get(c, 0.0) + math.exp(alt["logprob"])
    probs.setdefault(text, math.exp(tok["logprob"]))

    if all(l in probs for l in letters):
        total = sum(probs[l] for l in letters)
        out["normalized"] = probs[text] / total if total > 0 else None
        out["normalized_complete"] = True

    others = [p for l, p in probs.items() if l != text]
    if others:
        out["margin"] = math.log(probs[text]) - math.log(max(others))
    return out
