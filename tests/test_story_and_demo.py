"""Offline tests for the story, the demo routing and the app. No test makes a network call."""
import math
import sys

import pytest
from conftest import fake_response, tok

from mizan import client, demo as D, story as S
from mizan.config import ARTIFACTS_DIR, ROOT, experiment, prices
from mizan.parsing import parse_response

THRESHOLD = 6.249999994711611


@pytest.fixture
def res():
    return S.load_json(S.RESULTS)


def test_results_file_matches_the_approved_story(res):
    S.verify_approved_values(res)


def test_verify_stops_on_any_changed_value(res):
    res["original"]["mizan"]["accuracy"] = 0.80
    with pytest.raises(ValueError, match="Mizan accuracy"):
        S.verify_approved_values(res)


def test_exact_copy(res):
    h = S.hero_copy(res)
    assert h["metric_value"] + " " + h["metric_label"] == "66% LOWER MEASURED INFERENCE COST"
    assert h["proofs"] == ["+5.4 accuracy points vs always using the economical model",
                           "40% fewer accepted errors than matched random acceptance",
                           "Stable confidence after option-order shuffling"]
    assert h["evaluation"] == "Tested on 500 held-out Arabic questions not used during development."
    assert h["tradeoff"] == "MIZAN achieved 79.0% accuracy, compared with 82.6% for always using gpt-4.1."
    assert S.impact_copy(res) == ("Projected at one million similar tasks: approximately 746,000 handled without a large-model call.",
                                  "Projected from the 74.6% economical-model acceptance rate measured on held-out data.")
    assert S.directional_copy(res) == "+3.1 pts [-0.2, +6.0]"
    assert round(S.relative_error_reduction(res) * 100, 2) == 40.08


def test_robustness_rows_come_from_both_runs(res):
    assert S.robustness_rows(res) == [{"metric": "Accuracy", "original": "79.0%", "shuffled": "77.2%"},
                                      {"metric": "AUROC", "original": "0.8214", "shuffled": "0.8248"},
                                      {"metric": "Handled share", "original": "74.6%", "shuffled": "75.0%"},
                                      {"metric": "Saving", "original": "66.45%", "shuffled": "67.17%"}]


def test_offline_recompute_matches_every_recorded_value():
    diffs, checked = S.recompute_differences()
    assert diffs == []
    assert checked > 250


def test_replay_over_all_items_reproduces_the_results(res):
    t = S.replay_totals(S.replay_rows(S.load_json(S.PER_ITEM), res["original"]["n"]))
    assert t["escalated"] == res["original"]["mizan"]["escalated_items"]
    assert t["accuracy"] == res["original"]["mizan"]["accuracy"]
    assert math.isclose(t["mizan_cost_usd"], res["original"]["mizan"]["total_cost_usd"])
    assert math.isclose(t["always_large_cost_usd"], res["original"]["singles"][S.LARGE]["total_cost_usd"])


def test_readme_is_generated_from_the_results(res):
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_readme
    assert (ROOT / "README.md").read_text(encoding="utf-8") == build_readme.render(res)


def test_public_text_avoids_forbidden_words():
    for path in (ROOT / "README.md", ROOT / "app" / "streamlit_app.py", ROOT / "src" / "mizan" / "story.py", ROOT / "src" / "mizan" / "demo.py"):
        text = path.read_text(encoding="utf-8").lower()
        text = "\n".join(line for line in text.splitlines() if not line.startswith("forbidden ="))
        for word in S.FORBIDDEN:
            assert word not in text, f"{word!r} in {path.name}"


def test_tracked_per_item_table_has_no_question_text():
    text = S.PER_ITEM.read_text(encoding="utf-8")
    assert not any("؀" <= ch <= "ۿ" for ch in text)


# ---------------------------------------------------------------- demo routing


def letters_entry(probs, chosen="A"):
    return [tok(chosen, probs[chosen], probs)]


def test_option_probabilities_match_the_frozen_margin():
    entries = letters_entry({"A": 0.7, " B": 0.2, "C": 0.05, "hello": 0.01})
    parsed = parse_response("A", entries, "ABCD")
    out = D.option_probabilities(entries, "ABCD")
    assert [p["letter"] for p in out] == ["A", "B", "C"]
    assert math.isclose(math.log(out[0]["probability"]) - math.log(out[1]["probability"]), parsed["margin"])


def test_threshold_is_strict_and_invalid_or_missing_margin_are_handled():
    assert D.should_escalate({"valid": True, "margin": THRESHOLD - 1e-9}, THRESHOLD)
    assert not D.should_escalate({"valid": True, "margin": THRESHOLD}, THRESHOLD)
    assert D.should_escalate({"valid": False, "margin": "not_available"}, THRESHOLD)
    assert not D.should_escalate({"valid": True, "margin": "not_available"}, THRESHOLD)


def row(i, margin, small=True, large=True, valid=True, subject="Math"):
    return {"id": str(i), "subject": subject, "margin": margin, "small_correct": small, "large_correct": large, "valid": valid}


def test_high_confidence_rule_excludes_religious_subjects_only():
    rows = [row(1, 30.0, subject="Islamic Studies"), row(2, 20.0, subject="History"), row(3, 0.5, small=False)]
    assert D.select_examples(rows, THRESHOLD)["high_confidence"]["id"] == "2"
    # The exclusion is for the high-confidence example; the lower-confidence rule is unchanged.
    rows = [row(2, 20.0), row(3, 0.5, small=False, subject="Islamic Studies")]
    assert D.select_examples(rows, THRESHOLD)["lower_confidence"]["id"] == "3"


def test_selection_rule_does_not_change_routing():
    item = {"valid": True, "margin": 30.0, "subject": "Islamic Studies"}
    assert not D.should_escalate(item, THRESHOLD)


def test_selection_rule_is_fixed_and_prefers_a_real_correction():
    rows = [row(1, "not_available"), row(2, 9.0), row(3, 12.0), row(4, 12.0), row(5, 12.0, small=False),
            row(6, 0.5, small=False, large=True), row(7, 0.1, small=False, large=False), row(8, 0.2, small=True)]
    chosen = D.select_examples(rows, THRESHOLD)
    assert chosen["high_confidence"]["id"] == "3"  # highest finite margin, lowest ID on the tie
    assert chosen["lower_confidence"]["id"] == "6"  # lower margins exist, but they are not corrections
    assert chosen["correction_available"]


def test_selection_rule_makes_no_correction_claim_without_one():
    chosen = D.select_examples([row(1, 9.0), row(2, 0.5, small=False, large=False), row(3, 0.2, small=True)], THRESHOLD)
    assert chosen["lower_confidence"]["id"] == "3"
    assert not chosen["correction_available"]


def test_correction_needs_a_key_a_wrong_first_answer_and_a_right_second_one():
    assert D.stronger_corrected("B", "A", "A")
    assert not D.stronger_corrected("A", "A", "A")
    assert not D.stronger_corrected("B", "C", "A")
    assert not D.stronger_corrected("B", "A", None)
    assert not D.stronger_corrected("B", None, "A")


@pytest.mark.skipif(not S.EXAMPLES.exists(), reason="demo_examples.json is built locally")
def test_examples_agree_with_the_per_item_table_and_the_rule():
    examples, per = S.load_json(S.EXAMPLES), S.load_json(S.PER_ITEM)
    high, low = examples["examples"]["high_confidence"], examples["examples"]["lower_confidence"]
    for ex in (high, low):
        k = per["ids"].index(ex["id"])
        assert ex["threshold"] == THRESHOLD
        assert ex["margin"] == per["original"][S.SMALL]["margin"][k]
        assert ex["gpt_4o_mini"]["answer"] == per["original"][S.SMALL]["answer"][k]
        assert ex["cost_always_gpt_4_1_usd"] == per["original"][S.LARGE]["cost_usd"][k]
        assert ex["english"]["question"] and len(ex["english"]["options"]) == len(ex["options"])
    assert high["decision"] == D.HANDLED and high["answered_correctly"] and high["margin"] >= THRESHOLD
    assert low["decision"] == D.ESCALATED and low["margin"] < THRESHOLD
    assert low["stronger_model_corrected"] == (low["gpt_4o_mini"]["answer"] != low["correct_answer"] and low["gpt_4_1"]["answer"] == low["correct_answer"])


# ---------------------------------------------------------------- live path, with the network replaced


class FakeChat:
    def __init__(self, small, large):
        self.calls, self.small, self.large = [], small, large

    def __call__(self, payload, timeout, max_retries):
        self.calls.append(payload)
        return (self.small if payload["model"] == "gpt-4o-mini" else self.large), 0.01


ITEM = {"question": "q", "context": "", "options": ["a", "b", "c", "d"]}


def confident():
    return fake_response("A", letters_entry({"A": 0.9999, "B": 0.00001}), prompt_tokens=100, model="gpt-4o-mini-2024-07-18")


def unsure(letter="A"):
    other = "B" if letter == "A" else "A"
    return fake_response(letter, letters_entry({letter: 0.6, other: 0.4}, letter), prompt_tokens=100, model="snap")


@pytest.fixture
def isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DEMO_LEDGER", tmp_path / "demo_ledger.jsonl")
    return tmp_path / "demo_ledger.jsonl"


def test_live_handled_calls_only_the_small_model_with_frozen_settings(monkeypatch, isolated_ledger):
    fake = FakeChat(confident(), unsure())
    monkeypatch.setattr(client, "chat", fake)
    r = D.live_request(ITEM, experiment(), prices(), THRESHOLD)
    assert len(fake.calls) == 1 and fake.calls[0]["model"] == "gpt-4o-mini"
    call = experiment()["call"]
    assert fake.calls[0]["temperature"] == call["temperature"] and fake.calls[0]["top_logprobs"] == call["top_logprobs"] and fake.calls[0]["max_tokens"] == call["max_output_tokens"]
    assert fake.calls[0]["messages"][0]["content"] == experiment()["prompt"]["system"]
    assert r["decision"] == D.HANDLED and r["final_answer"] == "A" and r["large"] is None and not r["corrected"]
    assert r["always_large_cost_kind"] == "estimated"
    assert math.isclose(r["cost_usd"], 100 / 1e6 * 0.15 + 1 / 1e6 * 0.60)
    assert math.isclose(r["always_large_cost_usd"], 100 / 1e6 * 2.0 + 1 / 1e6 * 8.0)
    assert len(isolated_ledger.read_text(encoding="utf-8").splitlines()) == 1


def test_live_escalated_pays_for_both_and_claims_correction_only_with_a_key(monkeypatch, isolated_ledger):
    monkeypatch.setattr(client, "chat", FakeChat(unsure("B"), unsure("A")))
    r = D.live_request({**ITEM, "answer": "A"}, experiment(), prices(), THRESHOLD)
    assert r["decision"] == D.ESCALATED and r["final_answer"] == "A" and r["corrected"]
    assert r["always_large_cost_kind"] == "measured"
    assert math.isclose(r["cost_usd"], r["small"]["cost_usd"] + r["large"]["cost_usd"])
    no_key = D.live_request(ITEM, experiment(), prices(), THRESHOLD)
    assert no_key["decision"] == D.ESCALATED and not no_key["corrected"]


def test_live_calls_do_not_touch_the_experiment_ledger(monkeypatch, isolated_ledger):
    before = (ARTIFACTS_DIR / "cost_ledger.jsonl").read_bytes()
    monkeypatch.setattr(client, "chat", FakeChat(confident(), unsure()))
    D.live_request(ITEM, experiment(), prices(), THRESHOLD)
    assert (ARTIFACTS_DIR / "cost_ledger.jsonl").read_bytes() == before


# ---------------------------------------------------------------- app, no key and no network


def page_text(at) -> str:
    return "\n".join(el.proto.body for el in at.get("html"))


@pytest.fixture
def app(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("MIZAN_DISABLE_LIVE", "1")
    monkeypatch.setenv("MIZAN_REPLAY_SECONDS", "0")
    monkeypatch.setattr(client, "chat", lambda *a, **k: pytest.fail("the app called the network"))
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=60)
    return at.run()


def test_app_renders_every_section_in_order_without_a_key(app, res):
    assert not app.exception
    text = page_text(app)
    order = ["Built for efficient Arabic AI at scale", "Does every Arabic task need the biggest model?", "66%", "LOWER MEASURED INFERENCE COST",
             "Tested on 500 held-out Arabic questions not used during development.", "How MIZAN routes", "Arabic application", "Demo",
             "Replay 100 held-out requests", "Replaying a recorded held-out evaluation run.", "Evidence", "Robustness",
             "Confidence quality remained stable after the options moved.", "Impact at scale", "approximately 746,000"]
    at = -1
    for phrase in order:
        pos = text.find(phrase, at + 1)
        assert pos > at, phrase
        at = pos
    assert "directional, not conclusive" in text and S.SPLIT_SENTENCE in text
    assert app.expander[-1].label == "Technical details" and not app.expander[-1].proto.expanded
    for word in S.FORBIDDEN:
        assert word not in text.lower()


@pytest.mark.skipif(not S.EXAMPLES.exists(), reason="demo_examples.json is built locally")
def test_app_shows_recorded_examples_with_honest_labels(app):
    assert "Recorded run" in page_text(app) and "Handled efficiently" in page_text(app)
    app.button(key="btn_low").click().run()
    assert not app.exception
    text = page_text(app)
    assert "Escalated to protect quality" in text and "Example from the held-out set" in text and "Recorded run" in text
    assert "so it corrected the answer" in text


def test_app_replay_ends_on_the_recorded_totals(app):
    t = S.replay_totals(S.replay_rows(S.load_json(S.PER_ITEM)))
    app.button(key="btn_replay").click().run()
    assert not app.exception
    text = page_text(app)
    assert f">{t['handled']}<" in text and f">{t['escalated']}<" in text and f"{t['accuracy'] * 100:.1f}%" in text
