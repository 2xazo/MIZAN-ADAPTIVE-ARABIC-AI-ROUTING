"""Option-order perturbation on synthetic items. No network, and held-out is never read."""
import pytest

from mizan.data import LETTERS
from mizan.perturbation import (PERTURBATION_SEED, perturb_item, perturb_items, permutation_for, verify_item)
from mizan.prompts import build_messages


def item(i="q1", options=("alpha", "beta", "gamma", "delta"), answer="B", context="ctx"):
    return {"id": i, "subject": "s", "level": "l", "country": "c", "group": "g", "question": "question text",
            "context": context, "options": list(options), "answer": answer}


def many(n=200):
    sizes = [2, 3, 4, 5]
    return [item(f"q{i}", [f"opt{j}" for j in range(sizes[i % 4])], LETTERS[i % sizes[i % 4]]) for i in range(n)]


def answer_text(it):
    return it["options"][LETTERS.index(it["answer"])]


def test_question_context_and_option_texts_are_unchanged():
    for original in many():
        s = perturb_item(original)
        assert s["question"] == original["question"] and s["context"] == original["context"]
        assert sorted(s["options"]) == sorted(original["options"])
        assert len(s["options"]) == len(original["options"])


def test_answer_key_follows_the_correct_text():
    for original in many():
        s = perturb_item(original)
        assert answer_text(s) == answer_text(original)
        assert s["original_answer"] == original["answer"]
        assert LETTERS.index(s["answer"]) < len(s["options"])


def test_every_order_really_changes_including_two_options():
    shuffled, manifest = perturb_items(many())
    for original, s in zip(many(), shuffled):
        assert s["options"] != original["options"] and s["order_changed"]
    assert manifest["stayed_identical"] == 0 and manifest["n"] == 200


def test_duplicate_texts_still_change_the_displayed_order():
    original = item(options=("same", "same", "other"), answer="C")
    for i in range(50):
        s = perturb_item({**original, "id": f"d{i}"})
        assert s["options"] != original["options"] and answer_text(s) == "other"


def test_all_identical_options_are_recorded_not_hidden():
    _, manifest = perturb_items([item(options=("same", "same"), answer="A")])
    assert manifest["stayed_identical"] == 1


def test_fixed_seed_is_deterministic_and_independent_of_file_order():
    items = many(20)
    a, _ = perturb_items(items)
    b, _ = perturb_items(list(reversed(items)))
    assert a == list(reversed(b))
    assert permutation_for(["a", "b", "c", "d", "e"], "x", 1) == permutation_for(["a", "b", "c", "d", "e"], "x", 1)
    assert PERTURBATION_SEED == 20261030


def test_seed_changes_the_order_for_some_items():
    a = [perturb_item(it, seed=1)["options"] for it in many(50)]
    b = [perturb_item(it, seed=2)["options"] for it in many(50)]
    assert a != b


def test_permutation_maps_new_position_to_old():
    original = item()
    s = perturb_item(original)
    assert s["options"] == [original["options"][i] for i in s["option_permutation"]]


def test_input_item_is_not_modified():
    original = item()
    before = {**original, "options": list(original["options"])}
    perturb_item(original)
    assert original == before


def test_prompt_relabels_letters_with_the_new_order():
    original = item()
    s = perturb_item(original)
    user = build_messages(s, "sys")[1]["content"]
    for i, text in enumerate(s["options"]):
        assert f"{LETTERS[i]}. {text}" in user
    assert "Available choices: A, B, C, D" in user


@pytest.mark.parametrize("field,value,message", [
    ("question", "other", "question"), ("context", "other", "context"), ("id", "other", "id"),
    ("options", ["alpha", "beta", "gamma"], "number of options"),
    ("options", ["alpha", "beta", "gamma", "changed"], "option texts"),
    ("answer", "A", "correct answer text"),
])
def test_verify_catches_each_broken_guarantee(field, value, message):
    original = item()
    bad = {**perturb_item(original), field: value}
    if field == "answer":
        bad = {**original, "options": list(original["options"]), "answer": "A"}
    with pytest.raises(AssertionError, match=message):
        verify_item(original, bad)


def test_position_dependent_options_are_flagged_not_removed():
    arabic = item(options=("alpha", "beta", "gamma", "جميع ما سبق"))
    english = item("q2", options=("alpha", "beta", "gamma", "All of the above"))
    plain = item("q3")
    shuffled, manifest = perturb_items([arabic, english, plain])
    assert [s["position_dependent_option"] for s in shuffled] == [True, True, False]
    assert manifest["position_dependent_option"] == 2 and manifest["n"] == 3


def test_position_flag_ignores_ordinary_words():
    for text in ("وجود البروتينات في النواه", "كل ما تحصل عليه من المنشأة"):
        assert not perturb_item(item(options=(text, "beta", "gamma", "delta")))["position_dependent_option"]
    for text in ("كل ماسبق", "لا شيء مما سبق.", "أ و ب"):
        assert perturb_item(item(options=(text, "beta", "gamma", "delta")))["position_dependent_option"]


def test_shuffled_run_never_shares_the_original_cache(monkeypatch):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import run_eval
    from mizan.config import CACHE_DIR, DEV_FILE, HELDOUT_FILE, PERTURBATION_CACHE_DIR, PERTURBATION_FILE
    assert PERTURBATION_CACHE_DIR != CACHE_DIR
    assert run_eval.SPLITS["perturbation"] == (PERTURBATION_FILE, PERTURBATION_CACHE_DIR)
    assert run_eval.SPLITS["heldout"] == (HELDOUT_FILE, CACHE_DIR)
    assert run_eval.SPLITS["dev"] == (DEV_FILE, CACHE_DIR)
    monkeypatch.setattr(sys, "argv", ["run_eval.py", "--small", "a", "--large", "b", "--split", "perturbation"])
    monkeypatch.setattr(run_eval, "read_jsonl", lambda *_: pytest.fail("read items"))
    with pytest.raises(SystemExit, match="locked"):
        run_eval.main()


def test_build_script_is_locked_without_go(monkeypatch):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_perturbation
    monkeypatch.setattr(sys, "argv", ["build_perturbation.py"])
    monkeypatch.setattr(build_perturbation, "read_jsonl", lambda *_: pytest.fail("read held-out"))
    with pytest.raises(SystemExit, match="locked"):
        build_perturbation.main()
