import math

from conftest import tok
from mizan.parsing import NOT_AVAILABLE, parse_response


def test_valid_letter_raw_logprob():
    r = parse_response("B", [tok("B", 0.8, {"B": 0.8, "A": 0.1})], "ABCD")
    assert r["valid"] and r["letter"] == "B"
    assert math.isclose(r["raw_logprob"], math.log(0.8))
    assert r["skipped_whitespace_tokens"] == 0


def test_skips_leading_whitespace_token():
    r = parse_response(" C", [tok(" ", 0.9), tok("C", 0.7)], "ABCD")
    assert r["valid"] and r["letter"] == "C" and r["skipped_whitespace_tokens"] == 1


def test_extra_text_is_invalid():
    for content in ["Answer: A", "A.", "A because", "a", "F", ""]:
        r = parse_response(content, [tok(content or " ", 0.5)], "ABCD")
        assert not r["valid"], content


def test_letter_outside_this_question_is_invalid():
    assert not parse_response("E", [tok("E", 0.9)], "ABCD")["valid"]


def test_no_logprobs_is_invalid():
    r = parse_response("A", None, "ABCD")
    assert not r["valid"] and r["invalid_reason"] == "no_logprobs"


def test_normalized_only_when_all_options_visible_and_merges_space_variants():
    alts = {"A": 0.5, " A": 0.1, "B": 0.2, "C": 0.1, "D": 0.05, "\n": 0.05}
    r = parse_response("A", [tok("A", 0.5, alts)], "ABCD")
    assert r["normalized_complete"]
    assert math.isclose(r["normalized"], 0.6 / 0.95)
    assert math.isclose(r["margin"], math.log(0.6) - math.log(0.2))


def test_normalized_absent_when_an_option_missing():
    r = parse_response("A", [tok("A", 0.7, {"A": 0.7, "B": 0.2})], "ABCD")
    assert not r["normalized_complete"] and r["normalized"] is None


def test_margin_not_available_without_competitor():
    r = parse_response("A", [tok("A", 0.99, {"A": 0.99, "\n": 0.01})], "ABCD")
    assert r["margin"] == NOT_AVAILABLE
