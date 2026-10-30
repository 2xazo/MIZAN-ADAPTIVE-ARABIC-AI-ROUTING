"""MIZAN product page. Run with: streamlit run app/streamlit_app.py

Every number is read from artifacts/heldout_results.json through mizan.story and mizan.page. Nothing is
re-evaluated. Only "Route with MIZAN" can make a live call, on a button press, when an API key exists.
"""
from __future__ import annotations

import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from mizan import demo as D, page as P, story as S  # noqa: E402
from mizan.client import ApiError  # noqa: E402
from mizan.config import experiment, prices  # noqa: E402
from mizan.costs import BudgetError  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:  # dotenv optional: the app then runs on recorded results unless the key is in the environment
    pass

LIVE_ERRORS = (ApiError, BudgetError, urllib.error.URLError, TimeoutError, OSError, RuntimeError)
FIELDS = ["try_q", "try_a", "try_b", "try_c", "try_d", "try_e"]
# First-paint heights only. Each iframe then sizes itself to its content.
TOP_HEIGHT, BOTTOM_HEIGHT = 3400, 5200


def source_version() -> float:
    """Changes when a template or result changes, so the cached documents rebuild."""
    files = list(P.WEB.iterdir()) + [S.RESULTS, S.PER_ITEM, S.EXAMPLES, P.APP_CONFIG]
    return max(f.stat().st_mtime for f in files if f.exists())


@st.cache_data
def load_documents(version: float) -> dict:
    res = S.load_json(S.RESULTS)
    S.verify_approved_values(res)
    examples = S.load_json(S.EXAMPLES) if S.EXAMPLES.exists() else None
    per_item = S.load_json(S.PER_ITEM)
    return {"res": res, "examples": examples, "css": P.shell_css(), "header": P.build_header(),
            "top": P.build_top(res, examples), "bottom": P.build_bottom(res, per_item, examples)}


def load_example(example: dict) -> None:
    """Fills the form from the recorded high-confidence example."""
    state = st.session_state
    state["try_q"] = example["question"]
    for key, option in zip(FIELDS[1:], example["options"] + ["", ""]):
        state[key] = option
    state.pop("free", None)


def try_section(docs: dict) -> None:
    examples, res = docs["examples"], docs["res"]
    state = st.session_state
    with st.container(key="try"):
        st.html('<div id="try"><span class="mz-try-label">Try it</span><div class="mz-try-title">Try your own question</div>'
                '<div class="mz-try-notes"><p>Prototype evaluated on Arabic multiple-choice tasks.</p>'
                '<p>Do not enter sensitive or personal information.</p></div></div>')
        with st.form("free_input", border=False):
            question = st.text_area("Question", key="try_q", height=96, max_chars=P.MAX_QUESTION_CHARS)
            options = []  # one row of columns per pair, so the fields keep A to E order when stacked on a phone
            for pair in (("A", "B"), ("C", "D"), ("E (optional)", None)):
                columns = st.columns(2)
                for column, name in zip(columns, pair):
                    if name:
                        options.append(column.text_input(f"Option {name}", key=f"try_{name[0].lower()}"))
            route_col, load_col, _ = st.columns([1.2, 1, 2])
            submitted = route_col.form_submit_button("Route with MIZAN", type="primary", width="stretch", key="btn_route")
            load_col.form_submit_button("Load example", width="stretch", key="btn_load", disabled=not examples,
                                        on_click=load_example, args=(examples["examples"]["high_confidence"],) if examples else None)
        if submitted:
            errors, cleaned = P.validate_free_input(question, options)
            if errors:
                state["free"] = {"errors": errors}
            elif not D.has_live_key():
                state["free"] = {"info": "This looks valid, but live routing is off because no API key is configured. Nothing was sent. The recorded demo above needs no key."}
            else:
                item = {"question": question.strip(), "context": "", "options": cleaned}
                try:
                    with st.spinner("Calling the economical model"):
                        state["free"] = {"result": D.live_request(item, experiment(), prices(), res["original"]["threshold"]), "options": cleaned}
                except LIVE_ERRORS as err:
                    state["free"] = {"errors": [f"The live call failed ({type(err).__name__}). Nothing was routed."]}
        free = state.get("free")
        if free and free.get("errors"):
            st.html('<ul class="mz-errors" role="alert">' + "".join(f"<li>{P.e(x)}</li>" for x in free["errors"]) + "</ul>")
        elif free and free.get("info"):
            st.html(f'<p class="mz-info" role="status">{P.e(free["info"])}</p>')
        elif free:
            card = P.result_card(free["result"], free["options"])
            st.html(card[:-len("</div>")] + f'<details><summary>View technical evidence</summary>{P.diagnostics(free["result"])}</details></div>')
        st.html('<p class="mz-try-notes" style="font-size:.84rem">Your text is sent to OpenAI when you route it. The threshold was set on multiple-choice exam questions, so other kinds of text are outside what was measured.</p>')


def main() -> None:
    st.set_page_config(page_title="MIZAN", page_icon=str(P.LOGO), layout="wide", initial_sidebar_state="collapsed")
    docs = load_documents(source_version())
    st.html(docs["css"])
    st.html(docs["header"])
    components.html(docs["top"], height=TOP_HEIGHT, scrolling=False)
    try_section(docs)
    components.html(docs["bottom"], height=BOTTOM_HEIGHT, scrolling=False)


main()
