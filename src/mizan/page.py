"""The product page's content, with no Streamlit in it.

Every number is read from the results files through `mizan.story`, never typed into a template.
`build_page` returns the complete HTML document for the page iframe.
`app/web/page.html` holds structure and copy only, and a test keeps percentages out of those files.
"""
from __future__ import annotations

import base64
import html
import json
import re

import yaml

from . import demo as D, story as S
from .config import ROOT
from .parsing import NOT_AVAILABLE
from .perturbation import permutation_for

WEB = ROOT / "app" / "web"
ASSETS = ROOT / "app" / "assets"
LOGO = ASSETS / "logo.png"
PLOTLY = ASSETS / "vendor" / "plotly-basic-2.35.2.min.js"
APP_CONFIG = ROOT / "config" / "app.yaml"
LETTERS = "ABCDE"
MAX_QUESTION_CHARS = 2000
MAX_OPTION_CHARS = 500
TOKEN = re.compile(r"\{\{(\w+)\}\}")
NAV = (("overview", "Overview"), ("problem", "Problem"), ("demo", "Demo"), ("results", "Results"), ("robustness", "Robustness"),
       ("impact", "Impact"), ("replay", "Replay"), ("technical", "Technical details"))
LOGO_MARK = ('<svg class="mark" viewBox="0 0 120 120" role="img" aria-label="MIZAN logo">'
             '<path d="M60 8 L68 16 L60 24 L52 16 Z" fill="#D0F94A"/>'
             '<line x1="60" y1="26" x2="60" y2="100" stroke="#FFFFFF" stroke-width="6" stroke-linecap="round"/>'
             '<line x1="40" y1="104" x2="80" y2="104" stroke="#FFFFFF" stroke-width="6" stroke-linecap="round"/>'
             '<line x1="18" y1="40" x2="102" y2="40" stroke="#FFFFFF" stroke-width="6" stroke-linecap="round"/>'
             '<line x1="18" y1="40" x2="18" y2="60" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round"/>'
             '<line x1="102" y1="40" x2="102" y2="60" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round"/>'
             '<path d="M3 60 A15 15 0 0 0 33 60 Z" fill="#00D49C"/>'
             '<path d="M87 60 A15 15 0 0 0 117 60 Z" fill="#00879F"/></svg>')


def e(text) -> str:
    return html.escape(str(text))


def pct(x: float, places: int = 2) -> str:
    return f"{x * 100:.{places}f}%"


def pts(x: float, places: int = 1) -> str:
    return f"{x * 100:+.{places}f}"


def ci_pct(c: list, places: int = 2) -> str:
    return f"{c[0] * 100:.{places}f}% to {c[1] * 100:.{places}f}%"


def ci_pts(c: list, places: int = 1) -> str:
    return f"{c[0] * 100:+.{places}f} to {c[1] * 100:+.{places}f} points"


def usd(x: float, places: int = 5) -> str:
    return f"${x:.{places}f}"


def prob(p: float) -> str:
    """Raw exp(logprob) can round just above 1, so the display caps at 100%."""
    p = min(p, 1.0)
    return "<0.01%" if p < 0.0001 else f"{p * 100:.3f}%"


def margin_text(m) -> str:
    if m == NOT_AVAILABLE:
        return "not available (no competing option)"
    return f"{m:.2e}" if abs(m) < 1e-4 else f"{m:.4f}"


def table(headers: list[str], rows: list[list]) -> str:
    head = "".join(f"<th>{e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def github_url() -> str:
    """The configured repository link, or "" so no link is drawn. Anything not https:// is ignored."""
    if not APP_CONFIG.exists():
        return ""
    url = str((yaml.safe_load(APP_CONFIG.read_text(encoding="utf-8")) or {}).get("github_url") or "").strip()
    return url if re.fullmatch(r"https://[^\s\"'<>]+", url) else ""


def request_saving(r: dict) -> float:
    return 1 - r["cost_usd"] / r["always_large_cost_usd"]


# ---------------------------------------------------------------- validation of the free-input form


def validate_free_input(question: str, options: list[str], known: str = "") -> tuple[list[str], list[str]]:
    """Returns (errors, cleaned options). At least two options, in letter order with no gaps. `known` is an optional option letter."""
    question, cleaned = (question or "").strip(), [(o or "").strip() for o in options]
    errors = []
    if not question:
        errors.append("Enter a question.")
    elif len(question) > MAX_QUESTION_CHARS:
        errors.append(f"Keep the question under {MAX_QUESTION_CHARS} characters.")
    filled = [o for o in cleaned if o]
    used = max((i + 1 for i, o in enumerate(cleaned) if o), default=0)
    missing = [LETTERS[i] for i, o in enumerate(cleaned[:used]) if not o]
    if len(filled) < 2:
        errors.append("Enter at least two options.")
    elif missing:
        errors.append(f"Fill in option{'s' if len(missing) > 1 else ''} {', '.join(missing)}.")
    if any(len(o) > MAX_OPTION_CHARS for o in filled):
        errors.append(f"Keep each option under {MAX_OPTION_CHARS} characters.")
    if len({o.casefold() for o in filled}) < len(filled):
        errors.append("Each option must be different.")
    if known and known not in LETTERS[:used]:
        errors.append(f"The known correct option {known} is not one of the options entered.")
    return errors, filled


# ---------------------------------------------------------------- the live result, shown only in the Demo section's live form


LIVE_NO_KEY = "Live mode is unavailable because OPENAI_API_KEY is not configured. The recorded examples remain available."
LIVE_ACCEPTED, LIVE_ESCALATED = "Accepted — no second model call", "Escalated — high-capability model called"
LIVE_BUTTON = "Try your own question — Live"
LIVE_FORM_NOTE = "Examples only preload the inputs. Routing is decided live."
LIVE_RESULT_NOTE = "Live product demonstration — not part of the reported held-out evaluation."
SAUDI_EXAMPLE = {"question": "ما عاصمة المملكة العربية السعودية؟",
                 "options": ["الرياض", "جدة", "مكة المكرمة", "الدمام"], "correct_answer": "A"}


def live_answer(label: str, letter: str | None, options: list[str], tone: str, missing: str = "No valid answer letter was returned.") -> str:
    if not letter:
        return f'<div class="answer {tone}"><div class="tag">{e(label)}</div><p class="none">{e(missing)}</p></div>'
    return (f'<div class="answer {tone}"><div class="tag">{e(label)}</div>'
            f'<div class="ar" dir="auto"><bdi class="letter">{e(letter)}</bdi> {e(options[LETTERS.index(letter)])}</div></div>')


def live_top_two(side: dict) -> str:
    return ", ".join(f'{p["letter"]} {prob(p["probability"])}' for p in side["option_probabilities"][:2]) or "Not available"


def live_margin(r: dict) -> str:
    return "not available (invalid output)" if not r["small_valid"] else margin_text(r["margin"])


def live_technical(r: dict) -> str:
    """Raw values for this one run. The only place in the live result that names a model."""
    small, large = r["small"], r["large"]
    signal = [["Top two options (economical model)", live_top_two(small)], ["Margin", live_margin(r)], ["Threshold (frozen)", repr(r["threshold"])],
              ["Decision", LIVE_ESCALATED if r["decision"] == D.ESCALATED else LIVE_ACCEPTED]]

    def call_row(sent_as, side):
        return [sent_as, side["model_returned"], side["input_tokens"], side["output_tokens"], usd(side["cost_usd"], 7), f'{side["latency_s"]:.2f} s']
    calls = [call_row(D.SMALL, small)] + ([call_row(D.LARGE, large)] if large else [])
    always_kind = "measured tokens of this run" if r["always_large_cost_kind"] == "measured" else "same tokens at its price"
    routes = [[f"Always {D.SMALL}", usd(small["cost_usd"], 7)], ["MIZAN, this run", usd(r["cost_usd"], 7)],
              [f"Always {D.LARGE} ({always_kind})", usd(r["always_large_cost_usd"], 7)]]
    return (f'<div class="live-tech"><h5>Technical details</h5>{table(["Measure", "Value"], signal)}'
            f'<h5>Calls</h5>{table(["Sent as", "Model returned", "Input tokens", "Output tokens", "Cost", "Latency"], calls)}'
            f'<h5>Estimated cost per route</h5>{table(["Route", "Cost"], routes)}'
            f'<p class="live-fine">Costs use config/prices.yaml, verified on {e(r["prices_verified_on"])}. Latency was measured for this run only and is not an evaluation result.</p></div>')


def live_result(run: dict) -> str:
    """One live run, from `D.live_request`, with the question and options as the user typed them."""
    r, options, known = run["result"], run["options"], run["known"]
    escalated = r["decision"] == D.ESCALATED
    final = r["final_answer"]
    items = "".join(f'<li class="{"picked" if LETTERS[i] == final else ""}"><bdi class="letter">{LETTERS[i]}</bdi><span>{e(o)}</span></li>' for i, o in enumerate(options))
    answers = live_answer("Economical model answer", r["small_answer"], options, "amber" if escalated else "lime")
    no_final = "No final answer was returned."
    if escalated:
        answers += live_answer("High-capability model answer", r["large_answer"], options, "cyan", r["large_error"] or "No valid answer letter was returned.")
    answers += live_answer("Final answer", final, options, "cyan" if escalated else "lime", no_final)
    outcome = ""
    if known and final:
        right = final == known
        outcome = f'<div class="outcome {"ok" if right else "bad"}">{"Correct" if right else "Incorrect"}<span>Compared with the known correct option you entered ({e(known)})</span></div>'
    elif known:
        outcome = '<p class="live-fine">No final answer, so nothing was compared with the known correct option.</p>'
    decision = f'<span class="badge escalated">{LIVE_ESCALATED}</span>' if escalated else f'<span class="badge handled">{LIVE_ACCEPTED}</span>'
    return (f'<div class="live-result"><div class="live-head"><span class="badge live">LIVE API RUN</span>{decision}</div>'
            f'<div class="live-grid"><div class="question"><div class="tag">Your question</div><p class="ar q" dir="auto">{e(run["question"])}</p><ol class="opts ar" dir="auto">{items}</ol></div>'
            f'<div class="decision {"escalated" if escalated else "handled"}"><div class="answers">{answers}</div>{outcome}</div></div>{live_technical(r)}<p class="live-fine">{e(LIVE_RESULT_NOTE)}</p></div>')


# ---------------------------------------------------------------- the result card, shared by demo and free input


def plain_reason(r: dict) -> str:
    margin = r["margin"]
    if r["decision"] == D.HANDLED:
        return "The top answer led its closest rival by a wide gap."
    if margin == NOT_AVAILABLE or r["small_answer"] is None:
        return "The model did not return one valid answer."
    return "The model was split between two answers." if abs(margin) < 1 else "The gap between the top answer and its rival was too narrow."


def answer_block(label: str, letter: str | None, options: list[str], english: list[str] | None, tone: str = "") -> str:
    if not letter:
        return f'<div class="answer {tone}"><div class="tag">{e(label)}</div><p class="none">No valid answer letter was returned.</p></div>'
    i = LETTERS.index(letter)
    en = f'<div class="en">{e(english[i])}</div>' if english else ""
    return (f'<div class="answer {tone}"><div class="tag">{e(label)}</div>'
            f'<div class="ar" dir="rtl" lang="ar"><bdi class="letter">{e(letter)}</bdi> {e(options[i])}</div>{en}</div>')


def diagnostics(r: dict) -> str:
    """Raw values for one request, shown only inside technical sections."""
    small, large = r["small"], r["large"]

    def probs(side):
        return table(["Option", "Probability"], [[p["letter"], prob(p["probability"])] for p in side["option_probabilities"][:5]])
    rows = [["gpt-4o-mini", small["model_returned"], small["input_tokens"], small["output_tokens"], usd(small["cost_usd"], 7)]]
    if large:
        rows.append(["gpt-4.1", large["model_returned"], large["input_tokens"], large["output_tokens"], usd(large["cost_usd"], 7)])
    out = (f'<p>Margin {e(margin_text(r["margin"]))} against threshold {r["threshold"]!r}. The request escalates when the margin is below the threshold.</p>'
           f'<h5>gpt-4o-mini option probabilities (answered {e(r["small_answer"])})</h5>{probs(small)}')
    if large:
        out += f'<h5>gpt-4.1 option probabilities (answered {e(r["large_answer"])})</h5>{probs(large)}'
    return out + f'<h5>Tokens and model IDs</h5>{table(["Sent as", "Model returned", "Input tokens", "Output tokens", "Cost"], rows)}'


def result_card(r: dict, options: list[str], english: list[str] | None = None, key: str | None = None) -> str:
    source = "Live call" if r["source"] == "live" else "Recorded run"
    head = f'<div class="result-head"><span class="source">{source}</span></div>'
    if r["decision"] == D.HANDLED:
        saving = request_saving(r)
        basis = "Compared with always gpt-4.1 at the same token counts." if r["always_large_cost_kind"] == "estimated" else "Compared with the recorded gpt-4.1 call for the same request."
        if key:
            verdict = f'<p class="verdict good">{"This answer matches the answer key." if r["final_answer"] == key else "This answer does not match the answer key."}</p>'
        else:
            verdict = '<p class="verdict">This question has no answer key, so the demo cannot say whether the answer is right.</p>'
        return (f'<div class="result handled">{head}<span class="badge handled">Handled efficiently</span>'
                f'<p class="reason">{e(plain_reason(r))}</p>{answer_block("Model answer", r["small_answer"], options, english, "lime")}{verdict}'
                f'<div class="facts"><div class="fact"><span class="fact-k">Large-model call</span><span class="fact-v lime">Avoided</span></div>'
                f'<div class="fact"><span class="fact-k">Saving for this request</span><span class="fact-v lime">{pct(saving, 1)}</span><span class="fact-n">{basis}</span></div></div></div>')
    if key:
        fixed = r["corrected"]
        verdict = ("The stronger model corrected the first answer, according to the answer key." if fixed
                   else "The stronger model did not correct the first answer, according to the answer key.")
        verdict = f'<p class="verdict {"good" if fixed else ""}">{verdict}</p>'
    else:
        verdict = '<p class="verdict">This question has no answer key, so the demo cannot say which answer is right.</p>'
    return (f'<div class="result escalated">{head}<span class="badge escalated">Escalated to protect quality</span>'
            f'<p class="reason">{e(plain_reason(r))}</p><div class="answers">'
            f'{answer_block("First model answer", r["small_answer"], options, english, "amber")}'
            f'{answer_block("Stronger model answer", r["large_answer"], options, english, "cyan")}</div>{verdict}'
            '<p class="note">Escalated requests can cost more individually; savings come from the requests that avoid escalation.</p></div>')


def question_card(ex: dict) -> str:
    en = ex["english"]
    answered = ex["final_answer"]
    opts = "".join(f'<li class="{"picked" if LETTERS[i] == answered else ""}"><bdi class="letter">{LETTERS[i]}</bdi><span>{e(o)}</span></li>' for i, o in enumerate(ex["options"]))
    opts_en = "".join(f'<li><span class="letter">{LETTERS[i]}</span><span>{e(o)}</span></li>' for i, o in enumerate(en["options"]))
    context = f'<p class="ar" dir="rtl" lang="ar">{e(ex["context"])}</p>' if ex["context"] else ""
    context_en = f'<p>{e(en["context"])}</p>' if en.get("context") else ""
    return (f'<div class="question"><div class="tag">{e(ex["label"])} &middot; {e(ex["subject"])}</div>{context}'
            f'<p class="ar q" dir="rtl" lang="ar">{e(ex["question"])}</p><ol class="opts ar" dir="rtl" lang="ar">{opts}</ol>'
            f'<details class="translation"><summary>Show English</summary><div class="tag">English translation (machine-assisted)</div>{context_en}<p>{e(en["question"])}</p><ol class="opts">{opts_en}</ol></details></div>')


def option_probability(side: dict, letter: str) -> float:
    return next(p["probability"] for p in side["option_probabilities"] if p["letter"] == letter)


def top_two(side: dict) -> str:
    """The two most probable options, in the stored order."""
    return " &middot; ".join(f'{e(p["letter"])} {prob(p["probability"])}' for p in side["option_probabilities"][:2])


def demo_decision(ex: dict) -> str:
    """The decision half of one demo screen: confidence meter, route taken, final answer, correct or incorrect."""
    small, large = ex["gpt_4o_mini"], ex["gpt_4_1"]
    chosen = option_probability(small, small["answer"])
    escalated = ex["decision"] == D.ESCALATED
    route = ['<span class="hop lime">gpt-4o-mini</span>']
    if escalated:
        route.append('<span class="hop cyan">gpt-4.1</span>')
    route.append('<span class="hop end">Answer returned</span>')
    verdict = "Correct" if ex["answered_correctly"] else "Incorrect"
    first = ""
    if escalated:
        first = (f'<div class="first-answer"><span>gpt-4o-mini answered <b>{e(small["answer"])}</b>, which was incorrect.</span>'
                 f'<span>gpt-4.1 answered <b>{e(large["answer"])}</b> at {prob(option_probability(large, large["answer"]))}.</span></div>') if ex["stronger_model_corrected"] else ""
    badge = '<span class="badge escalated">Escalated</span>' if escalated else '<span class="badge handled">Accepted</span>'
    reason = "The top two options were effectively tied, so MIZAN paid for the stronger model." if escalated else "The top answer led its closest rival by a wide gap, so no second call was made."
    return (f'<div class="decision {"escalated" if escalated else "handled"}">'
            f'<div class="meter-block"><div class="meter-top"><span>Economical model confidence</span><b>{prob(chosen)}</b></div>'
            f'<div class="meter"><i style="width:{min(chosen, 1.0) * 100:.3f}%"></i></div>'
            f'<div class="meter-note">Top two options: {top_two(small)}. Answered {e(small["answer"])}.</div></div>'
            f'<div class="reveal"><div class="decision-head">{badge}<span class="source">Recorded run</span></div><p class="reason">{reason}</p>'
            f'<div class="route-taken"><span class="k">Route taken</span><div class="hops">{"".join(route)}</div></div>{first}'
            f'{answer_block("Final answer", ex["final_answer"], ex["options"], None, "cyan" if escalated else "lime")}'
            f'<div class="outcome {"ok" if ex["answered_correctly"] else "bad"}">{verdict}<span>Checked against the answer key</span></div></div></div>')


def demo_panels(examples: dict | None) -> dict:
    if not examples:
        missing = '<p class="muted">The recorded examples are not present. Build them with python scripts/build_demo_assets.py.</p>'
        return {"demo_high": missing, "demo_low": missing}
    out = {}
    for token, role in (("demo_high", "high_confidence"), ("demo_low", "lower_confidence")):
        ex = examples["examples"][role]
        out[token] = question_card(ex) + demo_decision(ex)
    return out


# ---------------------------------------------------------------- metric detail panels


def detail(plain: str, how: str) -> str:
    return f'<div class="detail"><p>{plain}</p><dl><div><dt>How it was measured</dt><dd>{how}</dd></div></dl></div>'


def cost_basis(res: dict) -> str:
    return f"{S.COST_BASIS} Prices verified on {res['preflight']['prices_verified_on']}."


def metric_details(res: dict) -> dict:
    """Plain explanations for the page. Exact values and intervals live in Technical details."""
    o = res["original"]
    behind = abs(o["non_dominance"]["paired"][S.LARGE]["accuracy_diff"]["observed"]) * 100
    z, m = o["mizan"], o["mechanism"]
    accepted = o["n"] - z["escalated_items"]
    return {
        "detail_saving": detail(
            f"Across the held-out test, MIZAN cost {z['saving_vs_top'] * 100:.0f}% less than sending every request to the high-capability model.",
            f"{cost_basis(res)} Each strategy is priced from the same {o['n']} recorded requests. Escalated requests pay for both calls, and that is included."),
        "detail_points": detail(
            "MIZAN answered more questions correctly than always using the economical model on its own.",
            f"Accuracy on the same {o['n']} questions: {pct(z['accuracy'], 1)} for MIZAN and {pct(o['singles'][S.SMALL]['accuracy'], 1)} for the economical model alone."),
        "detail_errors": detail(
            "When MIZAN keeps the economical model's answer, that answer is wrong less often than if the same share of answers were kept at random.",
            f"MIZAN accepted {accepted} of {o['n']} answers, and {pct(m['selective_risk'])} of those were wrong. Accepting at random at the same rate would keep the model's overall error rate of {pct(m['random_acceptance_risk'])}."),
        "detail_large": detail(
            f"MIZAN gives up {behind:.1f} accuracy points against sending every request to the high-capability model, in exchange for the lower cost.",
            f"Accuracy on the same {o['n']} questions: {pct(z['accuracy'], 1)} for MIZAN and {pct(o['singles'][S.LARGE]['accuracy'], 1)} for the always-large baseline."),
        "detail_n": detail(
            f"The evaluation used {o['n']} Arabic multiple-choice questions that were not used during development.",
            "The threshold and the prompt were frozen before the run."),
    }


# ---------------------------------------------------------------- technical evidence


def _strategy_rows(r: dict) -> list[list]:
    out = [[f"Always {m}", pct(v["accuracy"]), ci_pct(v["accuracy_ci95"]), usd(v["total_cost_usd"]), pct(v["saving_vs_top"])] for m, v in r["singles"].items()]
    z = r["mizan"]
    out.append(["MIZAN", pct(z["accuracy"]), ci_pct(z["accuracy_ci95"]), usd(z["total_cost_usd"]), f"{pct(z['saving_vs_top'])} (95% CI {ci_pct(z['saving_ci95'])})"])
    out.append([f"Matched random (mean of {r['random']['seeds']} seeds)", pct(r["random"]["accuracy_mean"]), f"seed range {ci_pct(r['random']['accuracy_range95'])}",
                usd(r["random"]["total_cost_usd_mean"]), pct(1 - r["random"]["total_cost_usd_mean"] / r["singles"][S.LARGE]["total_cost_usd"])])
    return out


def _paired_rows(r: dict) -> list[list]:
    return [[f"Always {m}", pts(b["accuracy_diff"]["observed"]), ci_pts(b["accuracy_diff"]["ci95"]), f"{b['cost_diff']['observed']:+.5f}",
             f"{b['cost_diff']['ci95'][0]:+.5f} to {b['cost_diff']['ci95'][1]:+.5f}"] for m, b in r["non_dominance"]["paired"].items()]


def directional_exact(d: dict) -> str:
    return f"{d['observed'] * 100:+.1f} [{d['ci95'][0] * 100:+.1f}, {d['ci95'][1] * 100:+.1f}]".replace("-", "\u2212")


def test_line() -> str:
    t = S.test_summary()
    return f"{t['count']} automated tests, all passing on {t['date']} at commit {t['commit']}." if t else S.TEST_FALLBACK


def tech_summary(res: dict) -> str:
    """The values a technical reader asks for first, with nothing to open."""
    o, s, pre = res["original"], res["perturbation"], res["preflight"]
    mini = o["non_dominance"]["paired"][S.MID]["accuracy_diff"]
    def card(key, value, note):
        return f'<div class="tcard"><span class="tk">{key}</span><span class="tv">{value}</span><span class="tn">{note}</span></div>'
    cards = [card("Margin AUROC", f"{o['mechanism']['auroc']:.3f} \u2192 {s['mechanism']['auroc']:.3f}", "Original run to option-shuffled run. Exact values and descriptive intervals are under Confidence."),
             card("Frozen threshold", f"{o['threshold']:.2f}", f"Stored as {o['threshold']!r}. Set on development data and never changed."),
             card("MIZAN vs Random", directional_exact(o["mizan_minus_random"]), "Accuracy points with 95% CI: directional, not conclusive."),
             card(f"MIZAN vs {S.MID}", f"{mini['observed'] * 100:+.1f} [{mini['ci95'][0] * 100:+.1f}, {mini['ci95'][1] * 100:+.1f}]".replace("-", "\u2212"),
                  f"Accuracy points with 95% CI. The interval includes zero, and {S.MID} costs less ({usd(o['singles'][S.MID]['total_cost_usd'])} vs {usd(o['mizan']['total_cost_usd'])})."),
             card("Exact saving", pct(o["mizan"]["saving_vs_top"]), f"95% CI {ci_pct(o['mizan']['saving_ci95'])}. {usd(o['mizan']['total_cost_usd'])} vs {usd(o['singles'][S.LARGE]['total_cost_usd'])} for {S.LARGE}."),
             card("Commits", f"{e(pre['approved_commit'][:7])} / {e(pre['head'][:7])}", "Preregistration commit, then held-out run commit."),
             ]
    return (f'<p class="tech-lead">{e(S.CORE_SENTENCE_TECHNICAL)} {e(S.CONFIDENCE_CHECK)} MIZAN reads confidence from the first answer without calling a separate verifier. '
            f'It is a {e(S.ROUTING_LAYER)}.</p><div class="tech-cards">{"".join(cards)}</div>'
            f'<div class="tech-notes"><p>{e(S.SPLIT_SENTENCE)}</p><p>{e(test_line())}</p><p>{e(cost_basis(res))}</p></div>')


def demo_table(examples: dict | None) -> str:
    if not examples:
        return ""
    rows = []
    for title, role in (("High confidence", "high_confidence"), ("Lower confidence", "lower_confidence")):
        ex = examples["examples"][role]
        small, large = ex["gpt_4o_mini"], ex["gpt_4_1"]
        top = small["option_probabilities"][:2]
        rows.append([title, ex["id"], f"{top[0]['letter']} {prob(top[0]['probability'])}, {top[1]['letter']} {prob(top[1]['probability'])}", small["answer"],
                     "Correct" if small["answer"] == ex["correct_answer"] else "Incorrect", ex["decision"].capitalize(),
                     f"{large['answer']} {prob(option_probability(large, large['answer']))}" if large else "Not called", ex["final_answer"], "Correct" if ex["answered_correctly"] else "Incorrect"])
    return ('<h4>Exact demo values</h4>' + table(["Case", "ID", "gpt-4o-mini top two", "Its answer", "Result", "Route", "gpt-4.1 answer", "Final", "Result"], rows))


def _level_rows(r: dict) -> list[list]:
    return [[name, v["n"], pct(v["accuracy"], 1), ci_pct(v["accuracy_ci95"], 1), pct(v["escalation_rate"], 1)] for name, v in r["levels"].items()]


def tech_confidence(res: dict, examples: dict | None) -> str:
    o, s, c = res["original"], res["perturbation"], res["comparison"]
    m, pre = o["mechanism"], res["preflight"]
    d1 = s["mizan_minus_random"]
    mini = o["non_dominance"]["paired"][S.MID]["accuracy_diff"]
    aucs = [["Original", f"{m['auroc']:.4f}", f"{m['auroc_ci95_descriptive'][0]:.4f} to {m['auroc_ci95_descriptive'][1]:.4f}"],
            ["Options shuffled", f"{s['mechanism']['auroc']:.4f}", f"{s['mechanism']['auroc_ci95_descriptive'][0]:.4f} to {s['mechanism']['auroc_ci95_descriptive'][1]:.4f}"],
            ["Change", f"{c['auroc_change']:+.4f}", f"{c['auroc_change_ci95_descriptive'][0]:+.4f} to {c['auroc_change_ci95_descriptive'][1]:+.4f}"]]
    robust = [[r["metric"], r["original"], r["shuffled"]] for r in S.robustness_rows(res)]
    accepted_rows = [["Share accepted", pct(m["coverage"], 1)], ["Accuracy of accepted answers", pct(m["accepted_accuracy"])],
                     ["Error among accepted answers", pct(m["selective_risk"])], ["Error under matched random acceptance", pct(m["random_acceptance_risk"])],
                     ["Relative error reduction (the results file records no 95% CI for this ratio)", pct(S.relative_error_reduction(res))],
                     [f"{S.SMALL} error among escalated requests", pct(m["small_error_in_escalated"])]]
    raw = f'<p>Threshold as stored: {o["threshold"]!r}.</p>'
    if examples:
        for title, role in (("High-confidence example", "high_confidence"), ("Lower-confidence example", "lower_confidence")):
            raw += f'<h5>{title}</h5>{diagnostics(D.recorded_request(examples["examples"][role]))}'
    return ('<h4>The signal</h4><p>MIZAN reads the answer token\'s log probabilities and compares the top answer with its closest rival. The gap is the margin. '
            'A margin below the threshold, or an invalid output, escalates.</p>'
            f'<h4>Threshold</h4><p class="big-num">{o["threshold"]:.2f}</p><p>Set on development data before the held-out run and never changed. '
            f'It escalated {pct(o["mizan"]["achieved_escalation"], 1)} of held-out requests ({o["mizan"]["escalated_items"]} of {o["n"]}) against a {pct(pre["target_rate"], 0)} target on development data.</p>'
            f'<h4>Margin AUROC for {S.SMALL} correctness (descriptive intervals)</h4>{table(["Run", "AUROC", "95% CI"], aucs)}'
            f'<h4>Accepted answers</h4>{table(["Measure", "Value"], accepted_rows)}'
            f'<h4>MIZAN vs matched random</h4><p>{directional_exact(o["mizan_minus_random"])} points: directional, not conclusive. The interval includes zero. The preregistered primary result is "{e(o["primary"])}". On the option-shuffled run: {pts(d1["observed"])} points, 95% CI {ci_pts(d1["ci95"])}.</p>'
            f'<h4>MIZAN vs always {S.MID}</h4><p>MIZAN is {pts(mini["observed"])} points, 95% CI {ci_pts(mini["ci95"])}, on accuracy. That interval includes zero, so MIZAN is not shown to be more accurate than {S.MID}, and {S.MID} costs less.</p>'
            f'<h4>Option-order check</h4>{table(["Metric", "Original", "Options shuffled"], robust)}'
            f'<p>Option order changed {c["routing_decisions_changed"]} of {o["n"]} routing decisions, and MIZAN accuracy moved {pts(c["accuracy_change"])} points. The preregistered claims were that AUROC would not drop by more than 0.05 and that the gain over matched random would keep its sign. {"Both held." if c["claims"]["both_hold"] else "They did not both hold."}</p>'
            f'<details class="raw"><summary>Raw diagnostics</summary><div class="raw-body">{raw}</div></details>')


def tech_cost(res: dict, examples: dict | None) -> str:
    o, s, ops, pre = res["original"], res["perturbation"], res["operations"], res["preflight"]
    strategy_head = ["Strategy", "Accuracy", "95% CI", "Total cost", "Saving vs always gpt-4.1"]
    paired_head = ["MIZAN minus", "Accuracy (points)", "95% CI", "Cost (USD)", "95% CI"]
    rows = []
    if examples:
        for title, role in (("High confidence", "high_confidence"), ("Lower confidence", "lower_confidence")):
            ex = examples["examples"][role]
            small, large = ex["gpt_4o_mini"], ex["gpt_4_1"]
            tokens = f"{small['input_tokens']} in, {small['output_tokens']} out"
            rows.append([title, tokens, usd(ex["cost_of_request_usd"], 7), usd(ex["cost_always_gpt_4_1_usd"], 7), "Both calls paid" if large else "One call paid"])
    prices = "; ".join(f"{m} ${v['input']:.2f} input, ${v['output']:.2f} output" for m, v in pre["prices_per_1m"].items())
    return (f'<h4>Original run, {o["n"]} questions</h4>{table(strategy_head, _strategy_rows(o))}{table(paired_head, _paired_rows(o))}'
            f'<h4>Option-shuffled run, same {s["n"]} questions</h4>{table(strategy_head, _strategy_rows(s))}{table(paired_head, _paired_rows(s))}'
            f'<h4>Accuracy by level, original run</h4>{table(["Level", "Questions", "Accuracy", "95% CI", "Escalated"], _level_rows(o))}'
            f'<h4>Accuracy by level, option-shuffled run</h4>{table(["Level", "Questions", "Accuracy", "95% CI", "Escalated"], _level_rows(s))}'
            f'{demo_table(examples)}'
            f'<h4>The two demo requests</h4>{table(["Example", "gpt-4o-mini tokens", "Cost of this request", "Always gpt-4.1", "Calls"], rows)}'
            f'<h4>Prices per 1M tokens</h4><p>{e(prices)}, verified on {e(pre["prices_verified_on"])}.</p>'
            f'<h4>Total spend</h4><p>{usd(ops["ledger_total"])} across all recorded experiments, of which {usd(ops["ledger_delta"])} was the two held-out runs. Budget {usd(ops["budget"], 2)}.</p>')


def tech_models(res: dict) -> str:
    o, ops = res["original"], res["operations"]
    roles = {S.SMALL: "Answers first in MIZAN", S.MID: "Comparison only", S.LARGE: "Receives escalated requests"}
    rows = [[m, roles[m], next(iter(v)), v[next(iter(v))]] for m, v in res["snapshots"]["original"].items()]
    return (f'<h4>Models</h4>{table(["Sent as", "Role", "Model returned", "Calls in the original run"], rows)}'
            f'<h4>Calls</h4><p>{ops["calls_ok"]} successful calls from {ops["attempts"]} attempts across both runs. Invalid outputs in the original run: {o["mizan"]["invalid_outputs"]}. '
            f'Answers with no competing option in the original run: {o["mizan"]["not_available_margins"]}.</p>')


def tech_repro(res: dict, examples: dict | None) -> str:
    o, pre = res["original"], res["preflight"]
    man = res["perturbation_manifest"]
    license_text = examples["examples"]["high_confidence"]["license"] if examples else ""
    translated = examples["examples"]["high_confidence"]["english"]["translated_by"] if examples else ""
    rules = f'{e(examples["selection_rule"]["high_confidence"])} {e(examples["selection_rule"]["lower_confidence"])}' if examples else ""
    return (f'<h4>Decision</h4><p>{e(res["decision"])} {e(res["decision_reason"])}</p>'
            f'<h4>Split</h4><p>{e(S.SPLIT_SENTENCE)} Development and held-out data share no subject-by-level group, and results describe those 25 equally weighted groups, not ArabicMMLU as a whole.</p>'
            f'<h4>Commits</h4><p>Preregistration commit {e(pre["approved_commit"][:7])}. Held-out run commit {e(pre["head"][:7])}.</p><h4>Tests</h4><p>{e(test_line())}</p>'
            f'<h4>Statistics</h4><p>All confidence intervals are two-sided 95% percentile bootstraps with {o["non_dominance"]["paired"][S.SMALL]["iters"]} iterations and seed 42. The AUROC intervals are descriptive.</p>'
            f'<h4>Option-order perturbation</h4><p>{e(man["name"])}: seed {man["seed"]}, {man["n"]} questions, {man["answer_letter_changed"]} answer letters moved, {man["position_dependent_option"]} questions flagged as position-dependent and kept. Same questions and option texts, so this is not a new test set.</p>'
            '<h4>Replay</h4><p>The replay on this page reads the recorded per-item outcomes for all held-out requests. Nothing is called again.</p>'
            '<h4>Latency</h4><p>Latency is not a reported result. An investigation of the development runs found stalls that point to connection or network conditions, with an unproven cause, so recorded times should not be read as model speed. An escalated request waits for both calls.</p>'
            f'<h4>Demo examples</h4><p>Chosen by a fixed rule. {rules}</p>'
            f'<h4>Data and translation</h4><p>{e(license_text)} Translated by {e(translated)}.</p>')


# ---------------------------------------------------------------- data for the page's script


def replay_data(res: dict, per_item: dict) -> dict:
    o = res["original"]
    # The count is explicit so this never depends on a default in another module. A long-running
    # Streamlit server keeps imported modules in memory, so an older `story` can sit beside this file.
    rows = S.replay_rows(per_item, len(per_item["ids"]))
    totals = S.replay_totals(rows)
    if totals["processed"] != o["n"] or totals["escalated"] != o["mizan"]["escalated_items"] or totals["accuracy"] != o["mizan"]["accuracy"]:
        raise ValueError("The per-item table does not reproduce the recorded results: "
                         f"requests {totals['processed']} vs {o['n']}, escalated {totals['escalated']} vs {o['mizan']['escalated_items']}, "
                         f"accuracy {totals['accuracy']} vs {o['mizan']['accuracy']}.")
    top = totals["always_large_cost_usd"]
    return {"ids": per_item["ids"], "esc": [int(r["escalated"]) for r in rows], "ok": [int(r["correct"]) for r in rows],
            "cost": [r["cost_usd"] / top for r in rows], "always": [r["always_large_cost_usd"] / top for r in rows],
            "final": {"processed": str(o["n"]), "saving": pct(o["mizan"]["saving_vs_top"], 0), "accuracy": pct(o["mizan"]["accuracy"], 1),
                      "handled": pct(o["mechanism"]["coverage"], 1)}}


def chart_data(res: dict) -> dict:
    """Five points read from the results file. X is measured cost with the always-large baseline at 100."""
    o = res["original"]
    top = o["singles"][S.LARGE]["total_cost_usd"]

    def point(key, label, sub, accuracy, cost):
        rel = cost / top * 100
        name = f"{label}<br>{sub}" if sub else label
        return {"key": key, "label": label, "sub": sub, "x": rel, "y": accuracy,
                "tip": f"<b>{name}</b><br>Accuracy {accuracy * 100:.1f}%<br>Measured cost {rel:.1f} (always-large = 100)"}
    single = o["singles"]
    return {"points": [point(S.SMALL, "Always-economical", f"Economical model ({S.SMALL})", single[S.SMALL]["accuracy"], single[S.SMALL]["total_cost_usd"]),
                       point(S.MID, "Mid-size standalone", f"Mid-size model ({S.MID})", single[S.MID]["accuracy"], single[S.MID]["total_cost_usd"]),
                       point("mizan", "MIZAN", "", o["mizan"]["accuracy"], o["mizan"]["total_cost_usd"]),
                       point("random", "Matched random", "", o["random"]["accuracy_mean"], o["random"]["total_cost_usd_mean"]),
                       point(S.LARGE, "Always-large", f"High-capability model ({S.LARGE})", single[S.LARGE]["accuracy"], single[S.LARGE]["total_cost_usd"])],
            "small": S.SMALL, "mid": S.MID, "large": S.LARGE}


def scale_cards(res: dict) -> list[dict]:
    share = pct(res["original"]["mechanism"]["coverage"], 1)
    return [{"title": "Arabic request", "text": "An Arabic task arrives. Nothing is decided in advance."},
            {"title": "Economical model answers first", "text": f"An economical model answers first. {S.CONFIDENCE_CHECK}"},
            {"title": "Confidence is weighed", "text": "MIZAN compares the top answer with its closest rival. A wide gap is kept; a narrow gap or invalid output is escalated."},
            {"title": "High-capability model only if needed", "text": f"Only uncertain cases reach the high-capability model. On our held-out test, {share} never needed it."}]


def robustness_data(res: dict, examples: dict | None) -> dict:
    out = {"options": [], "shuffled_positions": []}
    if examples:
        ex = examples["examples"]["high_confidence"]
        perm, _ = permutation_for(ex["options"], ex["id"])
        out["options"] = ex["options"]
        out["shuffled_positions"] = [perm.index(i) for i in range(len(perm))]
    return out


ROBUST_ROW_PX = 60


def robust_markup(examples: dict | None) -> dict:
    """The option rows in their original order, so they show without the script."""
    options = examples["examples"]["high_confidence"]["options"] if examples else []
    rows = "".join(f'<div class="optrow" style="transform:translateY({i * ROBUST_ROW_PX}px)"><bdi class="letter">{LETTERS[i]}</bdi><span>{e(text)}</span></div>'
                   for i, text in enumerate(options))
    return {"robust_rows": rows, "robust_height": len(options) * ROBUST_ROW_PX}


def script_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


# ---------------------------------------------------------------- templates


def fill(template: str, tokens: dict) -> str:
    def swap(match):
        if match.group(1) not in tokens:
            raise KeyError(f"Template token without a value: {match.group(1)}")
        return str(tokens[match.group(1)])
    return TOKEN.sub(swap, template)


def tokens_for(res: dict, examples: dict | None) -> dict:
    o = res["original"]
    h = S.hero_copy(res)
    m, z = o["mechanism"], o["mizan"]
    paired = o["non_dominance"]["paired"][S.SMALL]["accuracy_diff"]["observed"]
    reduction = S.relative_error_reduction(res)
    claims = res["comparison"]["claims"]["both_hold"]
    url = github_url()
    tokens = {
        "eyebrow": e(h["eyebrow"]), "headline": e(h["headline"]), "subheadline": e(h["subheadline"]),
        "metric_value": e(h["metric_value"]), "metric_label": e(h["metric_label"]),
        "chip_points": f"{paired * 100:+.1f} pts vs always-economical", "chip_errors": f"{reduction * 100:.0f}% fewer errors among accepted answers", "chip_n": f"{o['n']} held-out questions",
        "tradeoff": f"{pct(z['accuracy'], 1)} MIZAN accuracy vs {pct(o['singles'][S.LARGE]['accuracy'], 1)} for the always-large baseline.",
        "humain_portfolio": e(S.HUMAIN_FIT[0]), "humain_adaptive": e(S.HUMAIN_FIT[1]), "humain_next": e(S.HUMAIN_FIT[2]),
        "cost_basis": e(cost_basis(res)), "routing_layer": e(S.ROUTING_LAYER), "core_sentence": e(S.CORE_SENTENCE),
        "card_saving": f"{z['saving_vs_top'] * 100:.0f}%", "card_points": f"{paired * 100:+.1f}", "card_large": f"{abs(o['non_dominance']['paired'][S.LARGE]['accuracy_diff']['observed']) * 100:.1f}",
        "errors_big": f"{reduction * 100:.0f}%", "error_mizan": pct(m["selective_risk"]), "error_random": pct(m["random_acceptance_risk"]),
        "error_mizan_w": f"{m['selective_risk'] / m['random_acceptance_risk'] * 100:.2f}",
        "robust_badge": "Preregistered robustness check passed" if claims else "Preregistered robustness check did not pass",
        "robust_badge_class": "pass" if claims else "fail",
        "impact_handled_share": pct(m["coverage"], 1), "impact_esc_share": pct(z["achieved_escalation"], 1),
        "impact_handled_w": f"{m['coverage'] * 100:.1f}", "impact_esc_w": f"{z['achieved_escalation'] * 100:.1f}",
        "impact_saving": f"{z['saving_vs_top'] * 100:.0f}%",
        "replay_n": str(o["n"]), "replay_accuracy": pct(z["accuracy"], 1),
        "impact_tasks": f"{S.PROJECTION_TASKS:,}", "impact_handled": f"{round(S.PROJECTION_TASKS * m['coverage']):,}",
        "impact_escalated": f"{S.PROJECTION_TASKS - round(S.PROJECTION_TASKS * m['coverage']):,}",
        "scale_title": e(scale_cards(res)[0]["title"]), "scale_text": e(scale_cards(res)[0]["text"]),
        **robust_markup(examples), "tech_summary": tech_summary(res), "tech_confidence": tech_confidence(res, examples), "tech_cost": tech_cost(res, examples),
        "tech_models": tech_models(res), "tech_repro": tech_repro(res, examples),
        "logo_mark": LOGO_MARK, "logo_png": base64.b64encode(LOGO.read_bytes()).decode(),
        "footer_github": f'<a class="flink" href="{e(url)}" target="_blank" rel="noopener">GitHub</a>' if url else "",
        "live_link": "",
    }
    return {**tokens, **metric_details(res), **demo_panels(examples)}


def _document(body_file: str, tokens: dict, data: dict, libraries: str = "") -> str:
    css = (WEB / "components.css").read_text(encoding="utf-8") + (WEB / "page.css").read_text(encoding="utf-8")
    js = (WEB / "page.js").read_text(encoding="utf-8")
    body = fill((WEB / body_file).read_text(encoding="utf-8"), tokens)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<style>{css}</style></head><body><div id="page">{body}</div>'
            f'{libraries}<script>window.MIZAN={script_json(data)};</script><script>{js}</script></body></html>')


def build_page(res: dict, per_item: dict, examples: dict | None, live: bool = False) -> str:
    """`live` adds the Demo section's link to the Live Lab, which is a Streamlit section after this iframe."""
    data ={"scale": scale_cards(res), "replay": replay_data(res, per_item), "chart": chart_data(res), "robust": robustness_data(res, examples),
            "impact": {"handled": res["original"]["mechanism"]["coverage"]}}
    link = f'<div class="live-go"><a class="btn primary" href="#live" data-go="live">{LIVE_BUTTON}</a></div>'
    tokens = {**tokens_for(res, examples), "live_link": link if live else ""}
    return _document("page.html", tokens, data, f"<script>{PLOTLY.read_text(encoding='utf-8')}</script>")


def build_header() -> str:
    url = github_url()
    button = f'<a class="mz-gh" href="{e(url)}" target="_blank" rel="noopener">View GitHub</a>' if url else ""
    links = "".join(f'<a href="#{target}">{label}</a>' for target, label in NAV)
    return f'<header class="mz-head"><a class="mz-brand" href="#top" aria-label="MIZAN, back to top"><span class="mark"></span><span>MIZAN</span></a><nav aria-label="Page sections">{links}</nav>{button}</header>'


def shell_css() -> str:
    # st.html removes inline SVG, so the header mark is the same SVG as a CSS background.
    mark = base64.b64encode(LOGO_MARK.replace('<svg class="mark" ', '<svg xmlns="http://www.w3.org/2000/svg" ').encode()).decode()
    return ('<style>' + (WEB / "components.css").read_text(encoding="utf-8") + (WEB / "shell.css").read_text(encoding="utf-8")
            + f'.mz-brand .mark {{ background: url("data:image/svg+xml;base64,{mark}") center / contain no-repeat; }}</style>')
