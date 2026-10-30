"""MIZAN demo. Run with: streamlit run app/streamlit_app.py

Every number is read from artifacts/heldout_results.json through mizan.story. Nothing is re-evaluated.
A live call happens only on a button press, when an API key exists.
"""
from __future__ import annotations

import html
import os
import sys
import time
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from mizan import demo as D, story as S  # noqa: E402
from mizan.client import ApiError  # noqa: E402
from mizan.config import experiment, prices  # noqa: E402
from mizan.costs import BudgetError  # noqa: E402
from mizan.parsing import NOT_AVAILABLE  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:  # dotenv optional: the app then runs on recorded results unless the key is in the environment
    pass

BG, PANEL, LIME, CYAN, AMBER, WHITE, MUTED = "#0B2E30", "#12474B", "#C6F23A", "#2EC4D6", "#F5A524", "#FFFFFF", "#A9C4C6"
REPLAY_SECONDS = float(os.environ.get("MIZAN_REPLAY_SECONDS", "10"))
MAX_QUESTION_CHARS = 2000
LETTERS = "ABCDE"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@400;600;700&family=Inter:wght@400;500;600&family=Noto+Sans+Arabic:wght@400;500&display=swap');
.stApp {{ background: {BG}; }}
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stHeaderActionElements"] {{ display: none; }}
.stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp summary {{ font-family: 'Inter', 'Noto Sans Arabic', 'Segoe UI', sans-serif; }}
.stApp .block-container {{ max-width: 1080px; padding: 3.5rem 1rem 5rem; }}
.m h1, .m h2, .m .num {{ font-family: 'Unbounded', 'Inter', sans-serif; color: {WHITE}; margin: 0; padding: 0; letter-spacing: 0; }}
.m {{ color: {WHITE}; font-size: 1rem; line-height: 1.55; }}
.m h1 {{ font-size: clamp(2rem, 5.2vw, 3.5rem); font-weight: 700; line-height: 1.12; max-width: 17ch; }}
.m h2 {{ font-size: clamp(1.25rem, 3vw, 1.75rem); font-weight: 600; line-height: 1.25; margin: 3.5rem 0 1rem; }}
.eyebrow {{ color: {LIME}; font-weight: 600; font-size: .9rem; margin-bottom: 1rem; }}
.sub {{ color: {MUTED}; font-size: 1.15rem; max-width: 60ch; margin-top: 1.25rem; }}
.muted {{ color: {MUTED}; }} .small {{ font-size: .875rem; }}
.metric {{ margin: 2.25rem 0 1.75rem; }}
.metric .num {{ color: {LIME}; font-size: clamp(4rem, 13vw, 7.5rem); font-weight: 700; line-height: 1; }}
.metric .lab {{ font-weight: 600; font-size: clamp(.95rem, 2.2vw, 1.25rem); margin-top: .5rem; }}
.grid {{ display: grid; gap: .75rem; }}
.g3 {{ grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
.g2 {{ grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
.g6 {{ grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }}
.panel {{ background: {PANEL}; border-radius: 8px; padding: 1.1rem 1.25rem; }}
.proof {{ border-left: 3px solid {LIME}; font-weight: 500; }}
.flow {{ display: flex; flex-wrap: wrap; align-items: stretch; gap: .5rem; }}
.step {{ background: {PANEL}; border-radius: 8px; padding: .85rem 1rem; flex: 1 1 130px; font-weight: 500; font-size: .95rem; display: flex; align-items: center; border-top: 3px solid {MUTED}; }}
.step.eco {{ border-top-color: {LIME}; }} .step.gate {{ border-top-color: {AMBER}; }} .step.strong {{ border-top-color: {CYAN}; }}
.arrow {{ color: {MUTED}; display: flex; align-items: center; font-size: 1.1rem; }}
@media (max-width: 640px) {{ .flow {{ flex-direction: column; }} .step {{ flex: none; }} .arrow {{ justify-content: center; transform: rotate(90deg); height: 1.25rem; }} }}
.ar {{ direction: rtl; text-align: right; font-family: 'Noto Sans Arabic', 'Segoe UI', sans-serif; font-size: 1.15rem; line-height: 1.8; }}
.en {{ color: {MUTED}; font-size: .95rem; }}
.opts {{ margin: .5rem 0 0; padding: 0; list-style: none; }}
.opts li {{ padding: .15rem 0; }}
.tag {{ color: {MUTED}; font-size: .8rem; font-weight: 600; margin-bottom: .6rem; }}
.badge {{ display: inline-block; border-radius: 6px; padding: .35rem .75rem; font-weight: 600; color: {BG}; }}
.badge.handled {{ background: {LIME}; }} .badge.escalated {{ background: {AMBER}; }}
.source {{ color: {MUTED}; font-size: .85rem; margin-left: .75rem; }}
.answer {{ font-size: 1.05rem; font-weight: 600; }}
.key {{ color: {MUTED}; font-size: .8rem; }}
.counter .num {{ font-size: clamp(1.05rem, 1.9vw, 1.3rem); font-weight: 600; display: block; margin-top: .35rem; }}
.counter .eco {{ color: {LIME}; }} .counter .esc {{ color: {AMBER}; }} .counter .strong {{ color: {CYAN}; }}
.bar {{ display: flex; gap: 2px; height: 10px; margin: .75rem 0; background: {PANEL}; border-radius: 4px; overflow: hidden; }}
.bar i {{ display: block; height: 100%; }}
.pair {{ display: flex; justify-content: space-between; gap: 1rem; padding: .55rem 0; border-top: 1px solid rgba(169,196,198,.25); }}
.pair:first-of-type {{ border-top: 0; }}
.pair b {{ font-weight: 600; }}
.big {{ font-family: 'Unbounded', 'Inter', sans-serif; font-size: clamp(1.25rem, 3.2vw, 1.9rem); font-weight: 600; line-height: 1.35; }}
.tw {{ overflow-x: auto; }}
.m table {{ border-collapse: collapse; width: 100%; font-size: .875rem; margin: .5rem 0 1.25rem; }}
.m th {{ color: {MUTED}; font-weight: 600; text-align: left; padding: .4rem .6rem .4rem 0; border-bottom: 1px solid rgba(169,196,198,.4); }}
.m td {{ padding: .4rem .6rem .4rem 0; border-bottom: 1px solid rgba(169,196,198,.15); vertical-align: top; }}
.m h3 {{ color: {WHITE}; font-size: 1rem; font-weight: 600; margin: 1.25rem 0 .25rem; padding: 0; font-family: 'Inter', sans-serif; }}
.stButton button {{ background: {PANEL}; color: {WHITE}; border: 1px solid rgba(169,196,198,.4); border-radius: 8px; font-weight: 500; }}
.stButton button:hover {{ border-color: {LIME}; color: {WHITE}; }}
.stButton button:focus-visible {{ outline: 2px solid {LIME}; outline-offset: 2px; }}
.stButton button[kind="primary"] {{ background: {LIME}; color: {BG}; border-color: {LIME}; font-weight: 600; }}
.stButton button[kind="primary"]:hover {{ color: {BG}; }}
.stButton button[kind="primary"] p {{ color: {BG}; }}
.stApp [data-testid="stExpander"] details {{ background: {PANEL}; border: 0; border-radius: 8px; }}
.stApp [data-testid="stExpander"] summary, .stApp [data-testid="stExpander"] summary p {{ color: {WHITE}; font-weight: 600; }}
.stApp textarea {{ background: {PANEL}; color: {WHITE}; direction: rtl; font-family: 'Noto Sans Arabic', 'Segoe UI', sans-serif; caret-color: {WHITE}; }}
.stApp [data-baseweb="textarea"], .stApp [data-baseweb="base-input"] {{ background: {PANEL}; border-color: rgba(169,196,198,.4); }}
.stApp label p {{ color: {MUTED}; }}
</style>
"""


def show(markup: str, target=None) -> None:
    (target or st).html(f'<div class="m">{markup}</div>')


def e(text) -> str:
    return html.escape(str(text))


def usd(x: float, places: int = 7) -> str:
    return f"${x:.{places}f}"


def pct(x: float, places: int = 2) -> str:
    return f"{x * 100:.{places}f}%"


def pts(x: float, places: int = 1) -> str:
    return f"{x * 100:+.{places}f}"


def ci_pct(c: list, places: int = 2) -> str:
    return f"[{c[0] * 100:.{places}f}%, {c[1] * 100:.{places}f}%]"


def ci_pts(c: list, places: int = 1) -> str:
    return f"[{c[0] * 100:+.{places}f}, {c[1] * 100:+.{places}f}]"


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


@st.cache_data
def load_all() -> tuple[dict, dict, dict | None]:
    res = S.load_json(S.RESULTS)
    S.verify_approved_values(res)
    examples = S.load_json(S.EXAMPLES) if S.EXAMPLES.exists() else None
    return res, S.load_json(S.PER_ITEM), examples


# ---------------------------------------------------------------- sections


def hero(res: dict) -> None:
    h = S.hero_copy(res)
    cards = "".join(f'<div class="panel proof">{e(p)}</div>' for p in h["proofs"])
    show(f'<div class="eyebrow">{e(h["eyebrow"])}</div><h1>{e(h["headline"])}</h1><p class="sub">{e(h["subheadline"])}</p>'
         f'<div class="metric"><div class="num">{e(h["metric_value"])}</div><div class="lab">{e(h["metric_label"])}</div></div>'
         f'<div class="grid g3">{cards}</div><p style="margin:1.5rem 0 .25rem">{e(h["evaluation"])}</p>'
         f'<p class="muted small" style="margin:0">{e(h["tradeoff"])}</p>')


def how_it_routes() -> None:
    steps = [("Arabic application", ""), ("MIZAN", ""), ("Economical model", "eco"), ("Confidence gate", "gate"), ("Stronger model when needed", "strong")]
    parts = []
    for i, (name, cls) in enumerate(steps):
        if i:
            parts.append('<div class="arrow" aria-hidden="true">&rarr;</div>')
        parts.append(f'<div class="step {cls}">{e(name)}</div>')
    show(f'<h2>How MIZAN routes</h2><div class="flow">{"".join(parts)}</div>')


def question_markup(ex: dict) -> str:
    en = ex["english"]
    options = "".join(f"<li><bdi>{LETTERS[i]}.</bdi> {e(o)}</li>" for i, o in enumerate(ex["options"]))
    options_en = "".join(f"<li>{LETTERS[i]}. {e(o)}</li>" for i, o in enumerate(en["options"]))
    context = f'<div class="ar">{e(ex["context"])}</div>' if ex["context"] else ""
    context_en = f'<p class="en">{e(en["context"])}</p>' if en.get("context") else ""
    return (f'<div class="panel"><div class="tag">{e(ex["label"])} &middot; {e(ex["subject"])}</div>{context}<div class="ar">{e(ex["question"])}'
            f'<ul class="opts">{options}</ul></div><hr style="border:0;border-top:1px solid rgba(169,196,198,.25);margin:.85rem 0">'
            f'<div class="tag">English translation</div>{context_en}<div class="en">{e(en["question"])}<ul class="opts">{options_en}</ul></div>'
            f'<div class="key" style="margin-top:.5rem">Translated by {e(en["translated_by"])}.</div></div>')


def result_markup(r: dict, options: list[str], english: list[str] | None, key: str | None) -> str:
    handled = r["decision"] == D.HANDLED
    badge = "Handled efficiently" if handled else "Escalated to protect quality"
    source = "Live call" if r["source"] == "live" else "Recorded run"
    final = r["final_answer"]
    answer, answer_en = "The stronger model did not return a valid letter.", ""
    if final:
        answer = f"<bdi>{final}.</bdi> {e(options[LETTERS.index(final)])}"
        if english:
            answer_en = f'<div class="en">{e(english[LETTERS.index(final)])}</div>'
    lines = []
    if key:
        lines.append("This answer matches the answer key." if final == key else f"This answer does not match the answer key ({e(key)}).")
    if r["corrected"]:
        lines.append(f"gpt-4o-mini answered {e(r['small_answer'])}, which was wrong. The stronger model answered {e(r['large_answer'])}, which is right, so it corrected the answer.")
    verdict = "".join(f'<p class="small" style="margin:.35rem 0 0">{x}</p>' for x in lines)
    always = usd(r["always_large_cost_usd"])
    note = ""
    if r["always_large_cost_kind"] == "estimated":
        note = '<p class="key" style="margin:.5rem 0 0">gpt-4.1 was not called for this request. Its cost is estimated from the same token counts at gpt-4.1 prices.</p>'
    elif not handled:
        note = '<p class="key" style="margin:.5rem 0 0">An escalated request pays for both calls, so it can cost more than gpt-4.1 alone. The saving comes from the requests that stay on the economical model.</p>'
    return (f'<div class="panel"><span class="badge {r["decision"]}">{badge}</span><span class="source">{source}</span>'
            f'<p style="margin:.85rem 0">{e(r["reason"])}</p><div class="tag" style="margin-bottom:.15rem">Final answer</div>'
            f'<div class="answer ar">{answer}</div>{answer_en}{verdict}'
            f'<div class="grid g2" style="margin-top:1rem"><div><div class="tag" style="margin-bottom:0">Cost of this request</div><div style="font-weight:600">{usd(r["cost_usd"])}</div></div>'
            f'<div><div class="tag" style="margin-bottom:0">Always gpt-4.1</div><div style="font-weight:600">{always}</div></div></div>{note}</div>')


def technical_markup(r: dict) -> str:
    small, large = r["small"], r["large"]
    def probs(side):
        return table(["Option", "Probability"], [[p["letter"], prob(p["probability"])] for p in side["option_probabilities"][:5]])
    rows = [["gpt-4o-mini", small["model_returned"], small["input_tokens"], small["output_tokens"], usd(small["cost_usd"])]]
    if large:
        rows.append(["gpt-4.1", large["model_returned"], large["input_tokens"], large["output_tokens"], usd(large["cost_usd"])])
    out = (f'<p>Margin {e(margin_text(r["margin"]))} vs threshold {r["threshold"]!r}. The request escalates when the margin is below the threshold.</p>'
           f'<h3>gpt-4o-mini option probabilities (answered {e(r["small_answer"])})</h3>{probs(small)}')
    if large:
        out += f'<h3>gpt-4.1 option probabilities (answered {e(r["large_answer"])})</h3>{probs(large)}'
    return out + f'<h3>Tokens and model IDs</h3>{table(["Sent as", "Model returned", "Input tokens", "Output tokens", "Cost"], rows)}'


def run_live(item: dict, res: dict) -> dict:
    return D.live_request(item, experiment(), prices(), res["original"]["threshold"])


LIVE_ERRORS = (ApiError, BudgetError, urllib.error.URLError, TimeoutError, OSError, RuntimeError)


def demo_section(res: dict, examples: dict | None) -> None:
    show("<h2>Demo</h2>")
    live = D.has_live_key()
    state = st.session_state
    state.setdefault("role", "high_confidence")
    state.setdefault("results", {})
    state.setdefault("notice", None)

    if examples:
        left, right = st.columns(2)
        pressed = None
        if left.button("High-confidence example", key="btn_high", width="stretch", type="primary" if state.role == "high_confidence" else "secondary"):
            pressed = "high_confidence"
        if right.button("Lower-confidence example", key="btn_low", width="stretch", type="primary" if state.role == "lower_confidence" else "secondary"):
            pressed = "lower_confidence"
        if pressed:
            state.role = pressed
            state.notice = None
            if live and pressed not in state.results:  # a saved live result is reused, so a rerun never pays twice
                ex = examples["examples"][pressed]
                try:
                    with st.spinner("Calling the economical model"):
                        state.results[pressed] = run_live({"question": ex["question"], "context": ex["context"], "options": ex["options"], "answer": ex["correct_answer"]}, res)
                except LIVE_ERRORS as err:
                    state.notice = f"The live call failed ({type(err).__name__}), so this shows the recorded run."
            st.rerun()

        ex = examples["examples"][state.role]
        result = state.results.get(state.role) or D.recorded_request(ex)
        q, a = st.columns(2)
        show(question_markup(ex), q)
        show(result_markup(result, ex["options"], ex["english"]["options"], ex["correct_answer"]), a)
        if state.notice:
            show(f'<p class="small muted">{e(state.notice)}</p>', a)
        with st.expander("Technical details"):
            show(technical_markup(result))
    else:
        show('<p class="muted">The recorded examples are not present. Build them with <code>python scripts/build_demo_assets.py</code>.</p>')

    show('<h2 style="font-size:1.1rem;margin-top:2rem">Try your own Arabic question</h2>')
    if not live:
        show('<p class="small muted">Your own question needs a live call. Add OPENAI_API_KEY to <code>.env</code> to enable it. Recorded examples work without a key.</p>')
    with st.form("free_input"):
        question = st.text_area("Arabic question", max_chars=MAX_QUESTION_CHARS, height=90)
        options_text = st.text_area("Options, one per line (2 to 5)", height=130)
        submitted = st.form_submit_button("Route this question", disabled=not live)
    show('<p class="key">Your text is sent to OpenAI. The threshold was set on multiple-choice exam questions, so other kinds of text are outside what was measured. Your own question has no answer key, so this demo cannot say whether its answer is right.</p>')
    if submitted:
        options = [o.strip() for o in options_text.splitlines() if o.strip()]
        if not question.strip() or not 2 <= len(options) <= 5:
            state.free = {"error": "Enter a question and 2 to 5 options, one per line."}
        else:
            try:
                with st.spinner("Calling the economical model"):
                    state.free = {"result": run_live({"question": question.strip(), "context": "", "options": options}, res), "options": options}
            except LIVE_ERRORS as err:
                state.free = {"error": f"The live call failed ({type(err).__name__}). Nothing was routed."}
    free = state.get("free")
    if free and free.get("error"):
        show(f'<p class="small" style="color:{AMBER}">{e(free["error"])}</p>')
    elif free:
        show(result_markup(free["result"], free["options"], None, None))
        with st.expander("Technical details", expanded=False):
            show(technical_markup(free["result"]))


def counters_markup(t: dict, total: int) -> str:
    def cell(label, value, cls=""):
        return f'<div class="panel counter"><div class="tag" style="margin:0">{label}</div><span class="num {cls}">{value}</span></div>'
    handled_w, esc_w = t["handled"] / total * 100, t["escalated"] / total * 100
    return (f'<div class="bar" role="img" aria-label="{t["handled"]} handled, {t["escalated"]} escalated"><i style="width:{handled_w}%;background:{LIME}"></i><i style="width:{esc_w}%;background:{AMBER}"></i></div>'
            f'<div class="grid g6">{cell("Processed", t["processed"])}{cell("Handled by economical model", t["handled"], "eco")}{cell("Escalated", t["escalated"], "esc")}'
            f'{cell("Mizan cost", usd(t["mizan_cost_usd"], 5))}{cell("Always gpt-4.1 cost", usd(t["always_large_cost_usd"], 5), "strong")}{cell("Accuracy", pct(t["accuracy"], 1))}</div>')


def replay_section(res: dict, per_item: dict) -> None:
    rows = S.replay_rows(per_item)
    final = S.replay_totals(rows)
    show(f'<h2>Replay {len(rows)} held-out requests</h2><p class="muted" style="margin:0 0 .75rem">Replaying a recorded held-out evaluation run.</p>')
    start = st.button("Start replay", key="btn_replay")
    board = st.empty()
    if start:
        for i in range(1, len(rows) + 1):
            show(counters_markup(S.replay_totals(rows[:i]), len(rows)), board)
            time.sleep(REPLAY_SECONDS / len(rows))
        st.session_state.replayed = True
    elif st.session_state.get("replayed"):
        show(counters_markup(final, len(rows)), board)
    else:
        show(counters_markup(S.replay_totals([]), len(rows)), board)
    o = res["original"]
    saving = 1 - final["mizan_cost_usd"] / final["always_large_cost_usd"]
    show(f'<p class="small muted" style="margin-top:.75rem">These are the first {len(rows)} of the {o["n"]} requests in run order, a fixed rule. '
         f'They saved {saving * 100:.1f}% at {final["accuracy"] * 100:.1f}% accuracy, a sample of the full result of {o["mizan"]["saving_vs_top"] * 100:.2f}% and {o["mizan"]["accuracy"] * 100:.1f}%.</p>')


def base_chart(chart, height: int):
    return (chart.properties(height=height, background=PANEL, padding={"left": 16, "right": 20, "top": 16, "bottom": 12})
            .configure_view(stroke=None)
            .configure_axis(labelColor=MUTED, titleColor=MUTED, labelFont="Inter", titleFont="Inter", labelFontSize=12, titleFontSize=12,
                            gridColor="rgba(169,196,198,0.15)", domainColor="rgba(169,196,198,0.4)", tickColor="rgba(169,196,198,0.4)"))


def evidence_section(res: dict) -> None:
    show("<h2>Evidence</h2>")
    style = {"Always gpt-4o-mini": (LIME, 130, "left", 11, 0), "Always gpt-4.1-mini": (MUTED, 130, "center", 0, -15),
             "Always gpt-4.1": (CYAN, 130, "right", -11, 0), "Matched Random": (MUTED, 130, "left", 11, 14), "Mizan": (WHITE, 420, "left", 16, 0)}
    df = pd.DataFrame(S.chart_points(res))
    df["Accuracy"] = df["accuracy"].map(lambda x: pct(x, 1))
    df["Total cost"] = df["cost_usd"].map(lambda x: usd(x, 5))
    x = alt.X("cost_usd:Q", title=f"Total cost for {res['original']['n']} requests (USD)", scale=alt.Scale(domain=[0, 0.1]), axis=alt.Axis(format="$.2f", tickCount=5, grid=False))
    y = alt.Y("accuracy:Q", title="Accuracy", scale=alt.Scale(domain=[0.7, 0.85]), axis=alt.Axis(format=".0%", tickCount=4))
    layers = []
    for name, (color, size, align, dx, dy) in style.items():
        part = df[df["strategy"] == name]
        ring = {"stroke": LIME, "strokeWidth": 3} if name == "Mizan" else {"stroke": PANEL, "strokeWidth": 2}
        layers.append(alt.Chart(part).mark_point(filled=True, color=color, size=size, opacity=1, **ring).encode(x=x, y=y, tooltip=["strategy", "Accuracy", "Total cost"]))
        layers.append(alt.Chart(part).mark_text(align=align, dx=dx, dy=dy, color=WHITE, font="Inter", fontSize=13 if name != "Mizan" else 14, fontWeight=600 if name == "Mizan" else 400).encode(x=x, y=y, text="strategy"))
    st.altair_chart(base_chart(alt.layer(*layers), 380), width="stretch")

    m = res["original"]["mechanism"]
    show('<h3 style="margin:1.75rem 0 .5rem;font-size:1rem;font-weight:600">Share of accepted answers that are wrong</h3>')
    bars = pd.DataFrame([{"group": "Mizan", "error": m["selective_risk"], "label": pct(m["selective_risk"]), "color": LIME},
                         {"group": "Matched random acceptance", "error": m["random_acceptance_risk"], "label": pct(m["random_acceptance_risk"]), "color": MUTED}])
    two_lines = "datum.value == 'Matched random acceptance' ? ['Matched random', 'acceptance'] : datum.value"  # keeps the bars wide at phone width
    y2 = alt.Y("group:N", title=None, sort=None, axis=alt.Axis(labelExpr=two_lines, domain=False, ticks=False))
    x2 = alt.X("error:Q", title=None, scale=alt.Scale(domain=[0, 0.32]), axis=None)
    bar = alt.Chart(bars).mark_bar(cornerRadiusEnd=4, size=26).encode(x=x2, y=y2, color=alt.Color("color:N", scale=None), tooltip=["group", "label"])
    text = alt.Chart(bars).mark_text(align="left", dx=8, color=WHITE, font="Inter", fontSize=13, fontWeight=600).encode(x=x2, y=y2, text="label")
    st.altair_chart(base_chart(bar + text, 110), width="stretch")


def robustness_section(res: dict) -> None:
    rows = S.robustness_rows(res)
    def column(title, key):
        lines = "".join(f'<div class="pair"><span class="muted">{e(r["metric"])}</span><b>{e(r[key])}</b></div>' for r in rows)
        return f'<div class="panel"><div class="tag">{title}</div>{lines}</div>'
    show(f'<h2>Robustness</h2><div class="grid g2">{column("Original", "original")}{column("Option-shuffled", "shuffled")}</div>'
         '<p style="margin-top:1rem">Confidence quality remained stable after the options moved.</p>')


def impact_section(res: dict) -> None:
    line, basis = S.impact_copy(res)
    show(f'<h2>Impact at scale</h2><div class="panel"><div class="big">{e(line)}</div><p class="muted small" style="margin:.75rem 0 0">{e(basis)}</p></div>')


def technical_section(res: dict) -> None:
    o, s, c, ops, pre = res["original"], res["perturbation"], res["comparison"], res["operations"], res["preflight"]
    def strategy_rows(r):
        out = [[f"Always {m}", pct(v["accuracy"]), ci_pct(v["accuracy_ci95"]), usd(v["total_cost_usd"], 5), pct(v["saving_vs_top"])] for m, v in r["singles"].items()]
        z = r["mizan"]
        out.append(["Mizan", pct(z["accuracy"]), ci_pct(z["accuracy_ci95"]), usd(z["total_cost_usd"], 5), f"{pct(z['saving_vs_top'])} {ci_pct(z['saving_ci95'])}"])
        out.append(["Matched Random (mean of 1000 seeds)", pct(r["random"]["accuracy_mean"]), f"seed range {ci_pct(r['random']['accuracy_range95'])}",
                    usd(r["random"]["total_cost_usd_mean"], 5), pct(1 - r["random"]["total_cost_usd_mean"] / r["singles"][S.LARGE]["total_cost_usd"])])
        return out
    def paired_rows(r):
        return [[f"Always {m}", pts(b["accuracy_diff"]["observed"]), ci_pts(b["accuracy_diff"]["ci95"]), f"{b['cost_diff']['observed']:+.5f}",
                 f"[{b['cost_diff']['ci95'][0]:+.5f}, {b['cost_diff']['ci95'][1]:+.5f}]"] for m, b in r["non_dominance"]["paired"].items()]
    strategy_head = ["Strategy", "Accuracy", "95% CI", "Total cost", "Saving vs Always gpt-4.1"]
    paired_head = ["Mizan minus", "Accuracy (points)", "95% CI", "Cost (USD)", "95% CI"]
    mini = o["non_dominance"]["paired"][S.MID]
    d0, d1 = o["mizan_minus_random"], s["mizan_minus_random"]
    aucs = [["Original", f"{o['mechanism']['auroc']:.4f}", f"[{o['mechanism']['auroc_ci95_descriptive'][0]:.4f}, {o['mechanism']['auroc_ci95_descriptive'][1]:.4f}]"],
            ["Option-shuffled", f"{s['mechanism']['auroc']:.4f}", f"[{s['mechanism']['auroc_ci95_descriptive'][0]:.4f}, {s['mechanism']['auroc_ci95_descriptive'][1]:.4f}]"],
            ["Change", f"{c['auroc_change']:+.4f}", f"[{c['auroc_change_ci95_descriptive'][0]:+.4f}, {c['auroc_change_ci95_descriptive'][1]:+.4f}]"]]
    ids = "; ".join(f"{m} returned {next(iter(v))}" for m, v in res["snapshots"]["original"].items())
    with st.expander("Technical details"):
        show(f'<h3>Decision</h3><p>{e(res["decision"])} {e(res["decision_reason"])}</p>'
             f'<h3>Margin AUROC for gpt-4o-mini correctness (descriptive intervals)</h3>{table(["Run", "AUROC", "95% CI"], aucs)}'
             f'<h3>Threshold</h3><p>{o["threshold"]!r}, set on development data before the held-out run and never changed. It escalated {pct(o["mizan"]["achieved_escalation"], 1)} of held-out requests ({o["mizan"]["escalated_items"]} of {o["n"]}) against a {pct(pre["target_rate"], 0)} target on development data.</p>'
             f'<h3>Mizan vs matched Random</h3><p>{e(S.directional_copy(res))}: directional, not conclusive. The interval includes zero. The preregistered primary result is "{e(o["primary"])}". On the option-shuffled run: {pts(d1["observed"])} pts {ci_pts(d1["ci95"])}.</p>'
             f'<h3>Comparison with gpt-4.1-mini</h3><p>Always gpt-4.1-mini costs less ({usd(o["singles"][S.MID]["total_cost_usd"], 5)} vs {usd(o["mizan"]["total_cost_usd"], 5)}). Mizan is {pts(mini["accuracy_diff"]["observed"])} pts {ci_pts(mini["accuracy_diff"]["ci95"])} on accuracy, and that interval includes zero, so Mizan is not shown to be more accurate than gpt-4.1-mini.</p>'
             f'<h3>Original run, {o["n"]} questions</h3>{table(strategy_head, strategy_rows(o))}{table(paired_head, paired_rows(o))}'
             f'<h3>Option-shuffled run, same {s["n"]} questions</h3>{table(strategy_head, strategy_rows(s))}{table(paired_head, paired_rows(s))}'
             f'<p>Option order changed {c["routing_decisions_changed"]} of {o["n"]} routing decisions, and Mizan accuracy moved {pts(c["accuracy_change"])} pts. All confidence intervals are two-sided 95% percentile bootstraps with 1000 iterations and seed 42.</p>'
             f'<h3>Model IDs</h3><p>{e(ids)}. Prices per 1M tokens: {e(prices_text(pre))}, verified on {e(pre["prices_verified_on"])}.</p>'
             f'<h3>Split</h3><p>{e(S.SPLIT_SENTENCE)} Development and held-out data share no subject-by-level group, and results describe those 25 equally weighted groups, not ArabicMMLU as a whole.</p>'
             f'<h3>Commits</h3><p>Preregistration {e(pre["approved_commit"][:7])}. Run {e(pre["head"][:7])}.</p>'
             f'<h3>Total cost</h3><p>{usd(ops["ledger_total"], 5)} across all recorded experiments, of which {usd(ops["ledger_delta"], 5)} was the two held-out runs. Budget {usd(ops["budget"], 2)}.</p>'
             '<h3>Latency</h3><p>Latency is not a reported result. An investigation of the development runs found stalls that point to connection or network conditions, with an unproven cause, so recorded times should not be read as model speed. An escalated request waits for both calls.</p>')


def prices_text(pre: dict) -> str:
    p = pre["prices_per_1m"]
    return "; ".join(f"{m} ${v['input']:.2f} input, ${v['output']:.2f} output" for m, v in p.items())


def main() -> None:
    st.set_page_config(page_title="MIZAN", layout="centered", initial_sidebar_state="collapsed")
    st.html(CSS)
    res, per_item, examples = load_all()
    hero(res)
    how_it_routes()
    demo_section(res, examples)
    replay_section(res, per_item)
    evidence_section(res)
    robustness_section(res)
    impact_section(res)
    show('<div style="height:2.5rem"></div>')
    technical_section(res)


main()
