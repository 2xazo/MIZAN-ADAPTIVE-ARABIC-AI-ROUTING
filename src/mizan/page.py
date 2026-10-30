"""The product page's content, with no Streamlit in it.

Every number is read from the results files through `mizan.story`, never typed into a template.
`build_top` and `build_bottom` return complete HTML documents for the two page iframes.
`app/web/*.html` holds structure and copy only, and a test keeps percentages out of those files.
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
FONTS = "https://fonts.googleapis.com/css2?family=Unbounded:wght@400;600;700&family=Inter:wght@400;500;600;700&family=Noto+Sans+Arabic:wght@400;500;600&display=swap"
TOKEN = re.compile(r"\{\{(\w+)\}\}")
LOGO_MARK = ('<svg class="mark" viewBox="0 0 120 120" role="img" aria-label="MIZAN logo">'
             '<path d="M60 8 L68 16 L60 24 L52 16 Z" fill="#C6F23A"/>'
             '<line x1="60" y1="26" x2="60" y2="100" stroke="#FFFFFF" stroke-width="6" stroke-linecap="round"/>'
             '<line x1="40" y1="104" x2="80" y2="104" stroke="#FFFFFF" stroke-width="6" stroke-linecap="round"/>'
             '<line x1="18" y1="40" x2="102" y2="40" stroke="#FFFFFF" stroke-width="6" stroke-linecap="round"/>'
             '<line x1="18" y1="40" x2="18" y2="60" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round"/>'
             '<line x1="102" y1="40" x2="102" y2="60" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round"/>'
             '<path d="M3 60 A15 15 0 0 0 33 60 Z" fill="#C6F23A"/>'
             '<path d="M87 60 A15 15 0 0 0 117 60 Z" fill="#2EC4D6"/></svg>')


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


def validate_free_input(question: str, options: list[str]) -> tuple[list[str], list[str]]:
    """Returns (errors, cleaned options). Options A to D are required, and E is optional."""
    question, cleaned = (question or "").strip(), [(o or "").strip() for o in options]
    errors = []
    if not question:
        errors.append("Enter a question.")
    elif len(question) > MAX_QUESTION_CHARS:
        errors.append(f"Keep the question under {MAX_QUESTION_CHARS} characters.")
    missing = [LETTERS[i] for i, o in enumerate(cleaned[:4]) if not o]
    if missing:
        errors.append(f"Fill in option{'s' if len(missing) > 1 else ''} {', '.join(missing)}.")
    filled = [o for o in cleaned if o]
    if any(len(o) > MAX_OPTION_CHARS for o in filled):
        errors.append(f"Keep each option under {MAX_OPTION_CHARS} characters.")
    if len(set(filled)) < len(filled):
        errors.append("Each option must be different.")
    return errors, filled


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
            f'<div class="translation"><div class="tag">English translation (machine-assisted)</div>{context_en}<p>{e(en["question"])}</p><ol class="opts">{opts_en}</ol></div></div>')


def demo_panels(examples: dict | None) -> dict:
    if not examples:
        missing = '<p class="muted">The recorded examples are not present. Build them with python scripts/build_demo_assets.py.</p>'
        return {"demo_high": missing, "demo_low": missing}
    out = {}
    for token, role in (("demo_high", "high_confidence"), ("demo_low", "lower_confidence")):
        ex = examples["examples"][role]
        out[token] = question_card(ex) + result_card(D.recorded_request(ex), ex["options"], ex["english"]["options"], ex["correct_answer"])
    return out


# ---------------------------------------------------------------- metric detail panels


def detail(plain: str, how: str, exact: str) -> str:
    return (f'<div class="detail"><p>{plain}</p><dl><div><dt>How it was measured</dt><dd>{how}</dd></div>'
            f'<div><dt>Exact value</dt><dd class="exact">{exact}</dd></div></dl></div>')


def metric_details(res: dict) -> dict:
    o = res["original"]
    z, m = o["mizan"], o["mechanism"]
    small = o["singles"][S.SMALL]
    paired, against_top = o["non_dominance"]["paired"][S.SMALL]["accuracy_diff"], o["non_dominance"]["paired"][S.LARGE]["accuracy_diff"]
    d = o["mizan_minus_random"]
    accepted = o["n"] - z["escalated_items"]
    return {
        "detail_saving": detail(
            f"Across the held-out test, MIZAN used {pct(1 - z['saving_vs_top'])} of the inference cost of sending every request to {S.LARGE}.",
            f"Each strategy is priced per token from the same {o['n']} recorded requests. The cost of escalated requests, which pay for both calls, is included in MIZAN's total.",
            f"{pct(z['saving_vs_top'])} lower. 95% CI {ci_pct(z['saving_ci95'])}."),
        "detail_points": detail(
            f"MIZAN answered more questions correctly than always using {S.SMALL}, the economical model on its own.",
            f"Accuracy on the same {o['n']} questions: {pct(z['accuracy'], 1)} for MIZAN and {pct(small['accuracy'], 1)} for always {S.SMALL}, compared with a paired bootstrap. "
            f"The trade-off is that MIZAN is {abs(against_top['observed']) * 100:.1f} points below always {S.LARGE}, 95% CI {ci_pts(against_top['ci95'])}.",
            f"{pts(paired['observed'], 2)} accuracy points. 95% CI {ci_pts(paired['ci95'])}."),
        "detail_errors": detail(
            "When MIZAN keeps the economical model's answer, that answer is wrong less often than if the same share of answers were kept at random.",
            f"MIZAN accepted {accepted} of {o['n']} answers, and {pct(m['selective_risk'])} of those were wrong. Accepting at random at the same rate would keep the model's overall error rate of {pct(m['random_acceptance_risk'])}.",
            f"{pct(S.relative_error_reduction(res))} fewer ({pct(m['selective_risk'])} vs {pct(m['random_acceptance_risk'])}). The results file records no 95% CI for this ratio. "
            f"The related overall accuracy gain over matched random is {pts(d['observed'])} points, 95% CI {ci_pts(d['ci95'])}, which is directional, not conclusive."),
        "detail_n": detail(
            f"The evaluation used {o['n']} Arabic multiple-choice questions that were not used during development.",
            f"{e(S.SPLIT_SENTENCE)} The threshold and the prompt were frozen before the run.",
            f"{o['n']} questions, one run per model. This is a count, so it has no confidence interval."),
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
            f'<h4>MIZAN vs matched random</h4><p>{e(S.directional_copy(res))}: directional, not conclusive. The interval includes zero. The preregistered primary result is "{e(o["primary"])}". On the option-shuffled run: {pts(d1["observed"])} points, 95% CI {ci_pts(d1["ci95"])}.</p>'
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
            f'<h4>Commits</h4><p>Preregistration {e(pre["approved_commit"][:7])}. Run {e(pre["head"][:7])}.</p>'
            f'<h4>Statistics</h4><p>All confidence intervals are two-sided 95% percentile bootstraps with {o["non_dominance"]["paired"][S.SMALL]["iters"]} iterations and seed 42. The AUROC intervals are descriptive.</p>'
            f'<h4>Option-order perturbation</h4><p>{e(man["name"])}: seed {man["seed"]}, {man["n"]} questions, {man["answer_letter_changed"]} answer letters moved, {man["position_dependent_option"]} questions flagged as position-dependent and kept. Same questions and option texts, so this is not a new test set.</p>'
            '<h4>Replay</h4><p>The replay on this page reads the recorded per-item outcomes for all held-out requests. Nothing is called again.</p>'
            '<h4>Latency</h4><p>Latency is not a reported result. An investigation of the development runs found stalls that point to connection or network conditions, with an unproven cause, so recorded times should not be read as model speed. An escalated request waits for both calls.</p>'
            f'<h4>Demo examples</h4><p>Chosen by a fixed rule. {rules}</p>'
            f'<h4>Data and translation</h4><p>{e(license_text)} Translated by {e(translated)}.</p>')


# ---------------------------------------------------------------- data for the page's script


def replay_data(res: dict, per_item: dict) -> dict:
    o = res["original"]
    rows = S.replay_rows(per_item)
    totals = S.replay_totals(rows)
    if totals["processed"] != o["n"] or totals["escalated"] != o["mizan"]["escalated_items"] or totals["accuracy"] != o["mizan"]["accuracy"]:
        raise ValueError("The per-item table does not reproduce the recorded results.")
    top = totals["always_large_cost_usd"]
    return {"ids": per_item["ids"], "esc": [int(r["escalated"]) for r in rows], "ok": [int(r["correct"]) for r in rows],
            "cost": [r["cost_usd"] / top for r in rows], "always": [r["always_large_cost_usd"] / top for r in rows],
            "final": {"processed": str(o["n"]), "saving": pct(o["mizan"]["saving_vs_top"]), "accuracy": pct(o["mizan"]["accuracy"], 1),
                      "handled": pct(o["mechanism"]["coverage"], 1), "cost": pct(1 - o["mizan"]["saving_vs_top"])}}


def chart_data(res: dict) -> dict:
    o = res["original"]
    top = o["singles"][S.LARGE]["total_cost_usd"]

    def point(key, label, short, acc, cost, low, high, range_label, share=None):
        rel = cost / top * 100
        tip = f"<b>{label}</b><br>Accuracy {acc * 100:.1f}% ({range_label} {ci_pct([low, high], 1)})<br>Relative cost {rel:.2f}"
        if share is not None:
            tip += f"<br>Handled economically {pct(share, 1)}"
        return {"key": key, "label": label, "short": short, "x": rel, "y": acc, "low": low, "high": high, "tip": tip}
    points = [point(m, f"Always {m}", m, v["accuracy"], v["total_cost_usd"], *v["accuracy_ci95"], "95% CI") for m, v in o["singles"].items()]
    share = o["mechanism"]["coverage"]
    r = o["random"]
    points.append(point("random", "Matched random", "Matched random", r["accuracy_mean"], r["total_cost_usd_mean"], *r["accuracy_range95"], "95% seed range", share))
    z = o["mizan"]
    points.append(point("mizan", "MIZAN", "MIZAN", z["accuracy"], z["total_cost_usd"], *z["accuracy_ci95"], "95% CI", share))
    paired = o["non_dominance"]["paired"][S.SMALL]["accuracy_diff"]["observed"]
    return {"points": points, "cost_callout": f"{z['saving_vs_top'] * 100:.0f}% lower cost", "acc_callout": f"{paired * 100:+.1f} accuracy points",
            "small": S.SMALL, "large": S.LARGE}


def scale_cards(res: dict) -> list[dict]:
    share = pct(res["original"]["mechanism"]["coverage"], 1)
    return [{"title": "Arabic request", "text": "An Arabic task arrives. Nothing is decided in advance."},
            {"title": "Small model answers first", "text": "An economical model answers first. Its answer comes with a confidence signal, with no additional model call."},
            {"title": "Confidence is weighed", "text": "MIZAN compares the top answer with its closest rival. A wide gap is kept; a narrow gap or invalid output is escalated."},
            {"title": "Large model only if needed", "text": f"Only uncertain cases reach the stronger model. On our held-out test, {share} never needed it."}]


def robustness_data(res: dict, examples: dict | None) -> dict:
    o, s = res["original"], res["perturbation"]
    out = {"original": f"{o['mechanism']['auroc']:.3f}", "shuffled": f"{s['mechanism']['auroc']:.3f}", "options": [], "shuffled_positions": []}
    if examples:
        ex = examples["examples"]["high_confidence"]
        perm, _ = permutation_for(ex["options"], ex["id"])
        out["options"] = ex["options"]
        out["shuffled_positions"] = [perm.index(i) for i in range(len(perm))]
    return out


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
        "chip_points": f"{paired * 100:+.1f} pts vs always-small", "chip_errors": f"{reduction * 100:.0f}% fewer accepted errors", "chip_n": f"{o['n']} held-out questions",
        "tradeoff": f"{pct(z['accuracy'], 1)} MIZAN accuracy vs {pct(o['singles'][S.LARGE]['accuracy'], 1)} for always {S.LARGE}.",
        "card_saving": f"{z['saving_vs_top'] * 100:.0f}%", "card_points": f"{paired * 100:+.1f}", "card_errors": f"{reduction * 100:.0f}%",
        "errors_big": f"{reduction * 100:.0f}%", "error_mizan": pct(m["selective_risk"]), "error_random": pct(m["random_acceptance_risk"]),
        "error_mizan_w": f"{m['selective_risk'] / m['random_acceptance_risk'] * 100:.2f}",
        "auroc_original": f"{m['auroc']:.3f}", "robust_badge": "Preregistered robustness check passed" if claims else "Preregistered robustness check did not pass",
        "robust_badge_class": "pass" if claims else "fail",
        "impact_handled_share": pct(m["coverage"], 1), "impact_esc_share": pct(z["achieved_escalation"], 1),
        "impact_handled_w": f"{m['coverage'] * 100:.1f}", "impact_esc_w": f"{z['achieved_escalation'] * 100:.1f}",
        "impact_saving": f"{z['saving_vs_top'] * 100:.0f}%",
        "replay_n": str(o["n"]), "tech_confidence": tech_confidence(res, examples), "tech_cost": tech_cost(res, examples),
        "tech_models": tech_models(res), "tech_repro": tech_repro(res, examples),
        "logo_mark": LOGO_MARK, "logo_png": base64.b64encode(LOGO.read_bytes()).decode(),
        "footer_github": f'<a class="flink" href="{e(url)}" target="_blank" rel="noopener">GitHub</a>' if url else "",
    }
    return {**tokens, **metric_details(res), **demo_panels(examples)}


def _document(body_file: str, tokens: dict, data: dict, libraries: str = "") -> str:
    css = (WEB / "components.css").read_text(encoding="utf-8") + (WEB / "page.css").read_text(encoding="utf-8")
    js = (WEB / "page.js").read_text(encoding="utf-8")
    body = fill((WEB / body_file).read_text(encoding="utf-8"), tokens)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<link href="{FONTS}" rel="stylesheet"><style>{css}</style></head><body><div id="page">{body}</div>'
            f'{libraries}<script>window.MIZAN={script_json(data)};</script><script>{js}</script></body></html>')


def build_top(res: dict, examples: dict | None) -> str:
    return _document("top.html", tokens_for(res, examples), {"scale": scale_cards(res)})


def build_bottom(res: dict, per_item: dict, examples: dict | None) -> str:
    data = {"replay": replay_data(res, per_item), "chart": chart_data(res), "robust": robustness_data(res, examples),
            "impact": {"handled": res["original"]["mechanism"]["coverage"]}}
    return _document("bottom.html", tokens_for(res, examples), data, f"<script>{PLOTLY.read_text(encoding='utf-8')}</script>")


def build_header() -> str:
    url = github_url()
    button = f'<a class="mz-gh" href="{e(url)}" target="_blank" rel="noopener">View GitHub</a>' if url else ""
    links = "".join(f'<a href="#{target}">{label}</a>' for target, label in (("overview", "Overview"), ("demo", "Demo"), ("results", "Results"), ("robustness", "Robustness"), ("how", "How it works")))
    return f'<header class="mz-head"><a class="mz-brand" href="#top" aria-label="MIZAN, back to top"><span class="mark"></span><span>MIZAN</span></a><nav aria-label="Page sections">{links}</nav>{button}</header>'


def shell_css() -> str:
    # st.html removes inline SVG, so the header mark is the same SVG as a CSS background.
    mark = base64.b64encode(LOGO_MARK.replace('<svg class="mark" ', '<svg xmlns="http://www.w3.org/2000/svg" ').encode()).decode()
    return (f'<style>@import url("{FONTS}");' + (WEB / "components.css").read_text(encoding="utf-8") + (WEB / "shell.css").read_text(encoding="utf-8")
            + f'.mz-brand .mark {{ background: url("data:image/svg+xml;base64,{mark}") center / contain no-repeat; }}</style>')
