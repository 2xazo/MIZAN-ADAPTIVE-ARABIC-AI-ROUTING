"""One prompt, identical for the small and the large model. No few-shot, no CoT."""
from __future__ import annotations

from .data import LETTERS


def valid_letters(item: dict) -> str:
    return LETTERS[: len(item["options"])]


def build_messages(item: dict, system_prompt: str) -> list[dict]:
    letters = valid_letters(item)
    parts = []
    if item.get("context"):
        parts.append(item["context"])
    parts.append(item["question"])
    parts.extend(f"{letters[i]}. {opt}" for i, opt in enumerate(item["options"]))
    parts.append(f"Available choices: {', '.join(letters)}")
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(parts)},
    ]
