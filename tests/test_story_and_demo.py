"""Offline tests for the story, the demo routing and the app. No test makes a network call."""
import copy
import json
import math
import re
import sys

import pytest
from conftest import fake_response, tok

from mizan import client, demo as D, page as P, story as S
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
    web = [f for f in (ROOT / "app" / "web").iterdir() if f.is_file()]
    for path in [ROOT / "README.md", ROOT / "app" / "streamlit_app.py", ROOT / "src" / "mizan" / "story.py", ROOT / "src" / "mizan" / "demo.py", ROOT / "src" / "mizan" / "page.py", *web]:
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


# ---------------------------------------------------------------- page content, no Streamlit


@pytest.fixture
def examples():
    return S.load_json(S.EXAMPLES) if S.EXAMPLES.exists() else None


def visible(document: str, drop_technical: bool = False) -> str:
    """The document's markup without scripts and styles, and optionally without the technical section."""
    text = re.sub(r"<(script|style)\b.*?</\1>", "", document, flags=re.S)
    return re.sub(r'<details class="tech".*?</details>\s*</div>\s*</section>', "", text, flags=re.S) if drop_technical else text


def script_data(document: str) -> dict:
    return json.loads(re.search(r"window\.MIZAN=(.*?);</script>", document, re.S).group(1).replace("<\\/", "</"))


def test_templates_hold_no_typed_results():
    for name in ("top.html", "bottom.html"):
        text = (P.WEB / name).read_text(encoding="utf-8")
        text = re.sub(r"\{\{\w+\}\}%?", "", text)
        assert not re.findall(r"\d+(?:\.\d+)?\s*%", text), name
        assert "$" not in text, name


def test_every_template_token_has_a_value(res, examples):
    assert "{{" not in visible(P.build_top(res, examples)) and "{{" not in visible(P.build_bottom(res, S.load_json(S.PER_ITEM), examples))
    with pytest.raises(KeyError, match="nope"):
        P.fill("{{nope}}", {})


def test_page_values_come_from_the_results_file(res, examples):
    per = S.load_json(S.PER_ITEM)
    top, bottom = P.build_top(res, examples), P.build_bottom(res, per, examples)
    for phrase in ("66%", "LOWER MEASURED INFERENCE COST", "+5.4 pts vs always-small", "40% fewer accepted errors", "500 held-out questions",
                   "79.0% MIZAN accuracy vs 82.6% for always gpt-4.1.", "+2.6 to +8.4 points", "40.08%"):
        assert phrase in visible(top), phrase
    for phrase in ("62.44% to 70.48%", "15.82%", "26.40%", "0.821", "Preregistered robustness check passed", "74.6%", "25.4%", "Projected from measured held-out routing rates."):
        assert phrase in visible(bottom), phrase
    changed = copy.deepcopy(res)
    changed["original"]["mechanism"]["coverage"] = 0.5
    assert "50.0% never needed it" in P.build_top(changed, examples)
    assert "50.0%" in visible(P.build_bottom(changed, per, examples))


def test_scale_cards_have_the_measured_share(res):
    cards = P.scale_cards(res)
    assert [c["title"] for c in cards] == ["Arabic request", "Small model answers first", "Confidence is weighed", "Large model only if needed"]
    assert cards[3]["text"] == "Only uncertain cases reach the stronger model. On our held-out test, 74.6% never needed it."


def test_forty_percent_detail_does_not_invent_an_interval(res):
    text = P.metric_details(res)["detail_errors"]
    assert "records no 95% CI" in text and "directional, not conclusive" in text


def test_dollars_stay_inside_the_technical_section(res, examples):
    per = S.load_json(S.PER_ITEM)
    top, bottom = P.build_top(res, examples), P.build_bottom(res, per, examples)
    assert "$" in visible(top)
    assert "$" not in visible(top, drop_technical=True)
    assert "$" not in visible(bottom)
    assert "$" not in json.dumps(script_data(bottom)["replay"])


def test_raw_values_only_in_raw_diagnostics(res, examples):
    conf = P.tech_confidence(res, examples)
    before, raw = conf.split('<details class="raw">')
    assert ">6.25<" in before and "6.2499" not in before and "e-08" not in before
    assert "6.249999994711611" in raw and ("e-08" in raw or not examples)


def test_replay_data_rebuilds_the_results_from_every_item(res):
    r = P.replay_data(res, S.load_json(S.PER_ITEM))
    o = res["original"]
    assert len(r["esc"]) == o["n"] == 500
    assert sum(r["esc"]) == o["mizan"]["escalated_items"]
    assert sum(r["ok"]) / 500 == o["mizan"]["accuracy"]
    assert math.isclose(1 - sum(r["cost"]) / sum(r["always"]), o["mizan"]["saving_vs_top"], rel_tol=1e-9)
    assert math.isclose(sum(r["always"]), 1.0)
    assert r["final"] == {"processed": "500", "saving": "66.45%", "accuracy": "79.0%", "handled": "74.6%", "cost": "33.55%"}


def test_replay_refuses_a_table_that_disagrees_with_the_results(res):
    wrong = copy.deepcopy(res)
    wrong["original"]["mizan"]["escalated_items"] += 1
    with pytest.raises(ValueError, match="does not reproduce"):
        P.replay_data(wrong, S.load_json(S.PER_ITEM))


def test_chart_uses_relative_cost_and_labels_each_interval(res):
    c = P.chart_data(res)
    by = {p["key"]: p for p in c["points"]}
    assert set(by) == {"gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1", "random", "mizan"}
    assert by["gpt-4.1"]["x"] == 100
    assert math.isclose(by["mizan"]["x"], (1 - res["original"]["mizan"]["saving_vs_top"]) * 100)
    assert by["mizan"]["low"] == res["original"]["mizan"]["accuracy_ci95"][0]
    assert "95% CI" in by["mizan"]["tip"] and "Handled economically 74.6%" in by["mizan"]["tip"] and "Relative cost 33.55" in by["mizan"]["tip"]
    assert "95% seed range" in by["random"]["tip"]
    assert (c["cost_callout"], c["acc_callout"]) == ("66% lower cost", "+5.4 accuracy points")
    assert all("$" not in p["tip"] for p in c["points"])


def test_robustness_order_is_the_recorded_shuffle(res, examples):
    r = P.robustness_data(res, examples)
    assert (r["original"], r["shuffled"]) == ("0.821", "0.825")
    if examples:
        assert sorted(r["shuffled_positions"]) == list(range(len(r["options"])))
        assert r["shuffled_positions"] != list(range(len(r["options"])))


@pytest.mark.skipif(not S.EXAMPLES.exists(), reason="demo_examples.json is built locally")
def test_demo_cards_use_the_recorded_data(examples):
    high, low = examples["examples"]["high_confidence"], examples["examples"]["lower_confidence"]
    accepted = P.result_card(D.recorded_request(high), high["options"], high["english"]["options"], high["correct_answer"])
    assert all(x in accepted for x in ("Handled efficiently", "Avoided", "92.5%", "Recorded run"))
    assert "$" not in accepted
    escalated = P.result_card(D.recorded_request(low), low["options"], low["english"]["options"], low["correct_answer"])
    assert all(x in escalated for x in ("Escalated to protect quality", "The model was split between two answers.", "First model answer", "Stronger model answer",
                                        "corrected the first answer", "savings come from the requests that avoid escalation"))
    assert "$" not in escalated
    assert "English translation (machine-assisted)" in P.question_card(high)
    uncorrected = {**D.recorded_request(low), "corrected": False}
    assert "did not correct" in P.result_card(uncorrected, low["options"], low["english"]["options"], low["correct_answer"])


def test_user_text_is_escaped_in_the_result_card():
    r = {"source": "live", "decision": D.HANDLED, "margin": 9.0, "small_answer": "A", "large_answer": None, "final_answer": "A", "corrected": False,
         "cost_usd": 1.0, "always_large_cost_usd": 2.0, "always_large_cost_kind": "estimated"}
    card = P.result_card(r, ["<img src=x onerror=alert(1)>", "b", "c", "d"])
    assert "<img" not in card and "&lt;img" in card and "Live call" in card and "no answer key" in card


def test_free_input_validation():
    assert P.validate_free_input("q", ["a", "b", "c", "d", ""]) == ([], ["a", "b", "c", "d"])
    assert P.validate_free_input(" q ", ["a", "b", "c", "d", "e"]) == ([], ["a", "b", "c", "d", "e"])
    errors, _ = P.validate_free_input("", ["", "", "", "", ""])
    assert errors == ["Enter a question.", "Fill in options A, B, C, D."]
    assert P.validate_free_input("q", ["a", "b", "", "d", ""])[0] == ["Fill in option C."]
    assert P.validate_free_input("q", ["a", "a", "c", "d", ""])[0] == ["Each option must be different."]
    assert "under" in P.validate_free_input("q" * (P.MAX_QUESTION_CHARS + 1), ["a", "b", "c", "d", ""])[0][0]
    assert "under" in P.validate_free_input("q", ["a" * (P.MAX_OPTION_CHARS + 1), "b", "c", "d", ""])[0][0]


def test_github_link_is_hidden_unless_a_real_https_url_is_configured(tmp_path, monkeypatch):
    cfg = tmp_path / "app.yaml"
    monkeypatch.setattr(P, "APP_CONFIG", cfg)
    assert P.github_url() == ""  # no file
    for bad in ('github_url: ""', "github_url: javascript:alert(1)", "github_url: http://example.com/x", 'github_url: "https://x.example/a b"'):
        cfg.write_text(bad, encoding="utf-8")
        assert P.github_url() == "", bad
        assert "View GitHub" not in P.build_header()
    cfg.write_text("github_url: https://github.com/example/mizan", encoding="utf-8")
    assert 'href="https://github.com/example/mizan"' in P.build_header()
    assert "View GitHub" in P.build_header()


def test_assets_exist_and_the_cover_is_not_embedded():
    assert P.LOGO.exists() and (P.ASSETS / "cover-reference.png").exists()
    assert "plotly.js (basic - minified) v2.35.2" in P.PLOTLY.read_text(encoding="utf-8")[:200]
    for name in ("top.html", "bottom.html", "page.css", "page.js"):
        assert "cover-reference" not in (P.WEB / name).read_text(encoding="utf-8")
    assert "cover-reference" not in (ROOT / "app" / "streamlit_app.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------- app, no key and no network


def page_text(at) -> str:
    parts = [el.proto.body for el in at.get("html")]
    parts += [el.proto.srcdoc for el in at.get("iframe")]
    return "\n".join(parts)


@pytest.fixture
def app(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("MIZAN_DISABLE_LIVE", "1")
    monkeypatch.setattr(client, "chat", lambda *a, **k: pytest.fail("the app called the network"))
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=60)
    return at.run()


def test_app_renders_every_section_in_order_without_a_key(app):
    assert not app.exception
    bodies = [el.proto.body for el in app.get("html")]
    frames = [el.proto.srcdoc for el in app.get("iframe")]
    header = next(b for b in bodies if "<header" in b)
    free = " ".join(b for b in bodies if "mz-try" in b and "<style" not in b)
    text = " ".join(visible(part) for part in (header, frames[0], free, frames[1]))
    order = ["mz-head", "Overview", "How it works", "Built for efficient Arabic AI at scale", "Does every Arabic task need the biggest model?", "66%", "LOWER MEASURED INFERENCE COST",
             "One million requests. One model?", "Always Large", "Always Small", "Saudi Arabia is building Arabic AI", "Confidence high",
             "Confidence low or invalid", "Economical model", "Confidence gate", "Stronger model", "High-confidence example", "View technical evidence", "Confidence", "Tokens &amp; Cost", "Models", "Reproducibility",
             "Try your own question", "Prototype evaluated on Arabic multiple-choice tasks.", "Do not enter sensitive or personal information.",
             "Recorded evaluation run", "500-question", "The balance MIZAN found", "fewer accepted errors", "Confidence held steady after the options moved", "Preregistered robustness check passed",
             "What this means at scale", "model selection becomes an infrastructure decision", "Answer economically", "Read confidence", "Escalate uncertainty", "Measure the trade-off",
             "Not every question needs the biggest model. MIZAN helps find the ones that do.", "MIZAN — Adaptive Arabic AI Routing", "Built solo by Abdulaziz Alothman", "HUMAIN Hackathon — Challenge 2", "Back to top"]
    at = -1
    for phrase in order:
        pos = text.find(phrase, at + 1)
        assert pos > at, phrase
        at = pos
    assert "directional, not conclusive" in text and S.SPLIT_SENTENCE in text
    assert "100 held-out" not in text and "first 100" not in text
    assert '<details class="tech" id="technical">' in text  # collapsed: no open attribute
    for word in S.FORBIDDEN:
        assert word not in text.lower()


def test_app_hides_the_github_links_with_the_default_config(app):
    text = page_text(app)
    assert "View GitHub" not in text and 'class="flink" href="https' not in text


def test_app_chart_and_scripts_are_embedded(app):
    frames = [el.proto.srcdoc for el in app.get("iframe")]
    assert len(frames) == 2
    assert "plotly.js (basic - minified)" in frames[1] and "plotly.js (basic - minified)" not in frames[0]
    assert script_data(frames[0])["scale"] and script_data(frames[1])["replay"]["final"]["saving"] == "66.45%"


def test_app_free_input_validates_and_sends_nothing_without_a_key(app):
    app.button(key="btn_route").click().run()
    assert not app.exception
    assert "Enter a question." in page_text(app) and "Fill in options A, B, C, D." in page_text(app)
    app.text_area(key="try_q").set_value("q")
    for key, value in zip("abcd", "wxyz"):
        app.text_input(key=f"try_{key}").set_value(value)
    app.button(key="btn_route").click().run()
    assert not app.exception
    assert "Nothing was sent" in page_text(app)


@pytest.mark.skipif(not S.EXAMPLES.exists(), reason="demo_examples.json is built locally")
def test_app_load_example_fills_the_form(app):
    app.button(key="btn_load").click().run()
    assert not app.exception
    high = S.load_json(S.EXAMPLES)["examples"]["high_confidence"]
    assert app.text_area(key="try_q").value == high["question"]
    assert [app.text_input(key=f"try_{k}").value for k in "abcd"] == high["options"]
    assert app.text_input(key="try_e").value == ""


def test_app_live_route_only_on_button_press_with_fake_network(monkeypatch, isolated_ledger):
    from streamlit.testing.v1 import AppTest
    monkeypatch.delenv("MIZAN_DISABLE_LIVE", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    fake = FakeChat(confident(), unsure())
    monkeypatch.setattr(client, "chat", fake)
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
    assert not at.exception and fake.calls == []  # opening the page never calls a model
    at.text_area(key="try_q").set_value("q")
    for key, value in zip("abcd", "wxyz"):
        at.text_input(key=f"try_{key}").set_value(value)
    at.button(key="btn_route").click().run()
    assert not at.exception and len(fake.calls) == 1
    text = page_text(at)
    assert "Handled efficiently" in text and "Live call" in text and "no answer key" in text
