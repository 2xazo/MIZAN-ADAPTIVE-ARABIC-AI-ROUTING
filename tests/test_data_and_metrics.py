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


def test_split_shares_strata_when_strata_count_is_a_multiple_of_the_assignment_period():
    # 40 strata and a 300/500 split: the old assignment pattern repeated every 8 dealt items, so each
    # stratum landed entirely in one split. This is the shape of the real data.
    items = [{"id": f"{s}-{i}", "subject": f"s{s}", "level": "l"} for s in range(40) for i in range(50)]
    dev, held = stratified_split(items, 300, 500, seed=42)
    assert len(dev) == 300 and len(held) == 500
    assert not {x["id"] for x in dev} & {x["id"] for x in held}
    in_dev, in_held = Counter(x["subject"] for x in dev), Counter(x["subject"] for x in held)
    assert len(in_dev) == len(in_held) == 40
    assert all(7 <= v <= 8 for v in in_dev.values())
    assert all(12 <= v <= 13 for v in in_held.values())


def test_split_keeps_exact_sizes_with_uneven_and_tiny_strata():
    items = [{"id": f"{s}-{i}", "subject": f"s{s}", "level": "l"} for s, n in enumerate((100, 9, 3, 2, 1)) for i in range(n)]
    dev, held = stratified_split(items, 20, 30, seed=7)
    assert len(dev) == 20 and len(held) == 30
    assert not {x["id"] for x in dev} & {x["id"] for x in held}
    for s in ("s0", "s1", "s2", "s3"):  # every stratum with at least two items reaches both splits
        assert any(x["subject"] == s for x in dev) and any(x["subject"] == s for x in held)


def test_split_is_independent_of_input_order_with_many_strata():
    items = [{"id": f"{s}-{i}", "subject": f"s{s}", "level": "l"} for s in range(40) for i in range(50)]
    first = stratified_split(items, 300, 500, seed=42)
    second = stratified_split(list(reversed(items)), 300, 500, seed=42)
    assert [x["id"] for x in first[1]] == [x["id"] for x in second[1]]


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
