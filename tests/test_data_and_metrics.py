from collections import Counter

from mizan.data import normalize_answer_key, normalize_row, stratified_split
from mizan.metrics import auroc
from mizan.prompts import build_messages


def test_answer_key_normalization():
    assert normalize_answer_key("B", 4) == "B"
    assert normalize_answer_key("ب", 4) == "B"
    assert normalize_answer_key("3", 4) == "C"
    assert normalize_answer_key("E", 4) is None      # option E does not exist
    assert normalize_answer_key(float("nan"), 4) is None


def test_row_rejects_and_accepts():
    base = {"ID": 1, "Question": "س؟", "Option 1": "a", "Option 2": "b", "Option 3": None,
            "Answer Key": "B", "Subject": "S", "Level": "L"}
    it, why = normalize_row(base)
    assert why is None and it["options"] == ["a", "b"] and it["answer"] == "B"
    assert normalize_row({**base, "Option 2": None})[1] == "fewer_than_2_options"
    assert normalize_row({**base, "Answer Key": "D"})[1] == "unmappable_answer_key"


def _items(n):
    return [{"id": str(i), "subject": f"s{i % 5}", "level": f"l{i % 3}"} for i in range(n)]


def test_split_disjoint_deterministic_and_stratified():
    items = _items(1000)
    d1, h1 = stratified_split(items, 300, 500, seed=42)
    d2, h2 = stratified_split(list(reversed(items)), 300, 500, seed=42)
    assert [x["id"] for x in d1] == [x["id"] for x in d2]
    assert len(d1) == 300 and len(h1) == 500
    assert not {x["id"] for x in d1} & {x["id"] for x in h1}
    for split, size in ((d1, 300), (h1, 500)):
        c = Counter(x["subject"] for x in split)
        assert all(abs(v - size / 5) <= 3 for v in c.values())


def test_auroc_known_values_and_ties():
    assert auroc([0.9, 0.8, 0.1, 0.2], [1, 1, 0, 0]) == 1.0
    assert auroc([0.1, 0.2, 0.9, 0.8], [1, 1, 0, 0]) == 0.0
    assert auroc([0.5, 0.5], [1, 0]) == 0.5
    assert auroc([float("-inf"), 0.3, 0.4], [0, 1, 1]) == 1.0
    assert auroc([1, 2], [1, 1]) is None


def test_prompt_lists_only_existing_letters():
    msgs = build_messages({"question": "q", "options": ["x", "y", "z"], "context": ""}, "SYS")
    assert "C. z" in msgs[1]["content"] and "D." not in msgs[1]["content"]
    assert msgs[1]["content"].endswith("Available choices: A, B, C")
