"""MIZAN product page. Run with: streamlit run app/streamlit_app.py

Every number is read from artifacts/heldout_results.json through mizan.story and mizan.page. Nothing is
re-evaluated. The live form is hidden unless MIZAN_LIVE_LAB=1. It then calls a model only on a button press, when an API key exists.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from mizan import demo as D, page as P, story as S  # noqa: E402
from mizan.config import experiment, prices  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:  # dotenv optional: the app then runs on recorded results unless the key is in the environment
    pass

FIELDS = ["try_q", "try_a", "try_b", "try_c", "try_d", "try_e"]
# First-paint height only. The iframe then sizes itself to its content.
PAGE_HEIGHT = 8000


def live_lab_enabled() -> bool:
    return os.environ.get("MIZAN_LIVE_LAB") == "1"


def source_version() -> float:
    """Changes when a template or result changes, so the cached documents rebuild."""
    files = list(P.WEB.iterdir()) + [S.RESULTS, S.PER_ITEM, S.EXAMPLES, P.APP_CONFIG]
    return max(f.stat().st_mtime for f in files if f.exists())


@st.cache_data
def load_documents(version: float, live: bool) -> dict:
    res = S.load_json(S.RESULTS)
    S.verify_approved_values(res)
    examples = S.load_json(S.EXAMPLES) if S.EXAMPLES.exists() else None
    per_item = S.load_json(S.PER_ITEM)
    return {"res": res, "examples": examples, "css": P.shell_css(), "header": P.build_header(),
            "page": P.build_page(res, per_item, examples, live)}


def load_example(example: dict) -> None:
    """Fills the form from the recorded high-confidence example. Never calls a model."""
    state = st.session_state
    state["try_q"] = example["question"]
    for key, option in zip(FIELDS[1:], example["options"] + ["", ""]):
        state[key] = option
    state["try_known"] = ""
    state.pop("live", None)


def toggle_form() -> None:
    st.session_state["live_open"] = not st.session_state.get("live_open", False)


def start_run() -> None:
    st.session_state["live_running"] = True
    st.session_state.pop("live", None)


def run_live(question: str, options: list[str], known: str, threshold: float) -> dict:
    """Validates, then makes the live request. Failures come back as messages, so the page and the recorded examples keep working."""
    errors, cleaned = P.validate_free_input(question, options, known)
    if errors:
        return {"errors": errors}
    if not D.has_live_key():
        return {"info": P.LIVE_NO_KEY}
    item = {"question": question.strip(), "context": "", "options": cleaned, "answer": known or None}
    try:
        with st.spinner("Running MIZAN..."):
            return {"result": D.live_request(item, experiment(), prices(), threshold), "question": item["question"], "options": cleaned, "known": known}
    except D.LIVE_ERRORS as err:
        return {"errors": [f"The live run failed. {D.failure_message(err)} Nothing was routed. The recorded examples remain available."]}


def live_section(docs: dict) -> None:
    state = st.session_state
    examples = docs["examples"]
    running = state.get("live_running", False)
    with st.container(key="live"):
        st.button("Try your own question — Live", key="btn_live", type="primary", on_click=toggle_form, disabled=running)
        if not state.get("live_open"):
            return
        st.html('<div class="mz-try-notes"><p>Prototype evaluated on Arabic multiple-choice tasks.</p>'
                '<p>Do not enter sensitive or personal information.</p></div>')
        has_key = D.has_live_key()
        if not has_key:
            st.html(f'<p class="mz-info" role="status">{P.e(P.LIVE_NO_KEY)}</p>')
        with st.form("live_form", border=False):
            question = st.text_area("Question", key="try_q", height=96, max_chars=P.MAX_QUESTION_CHARS)
            options = []  # one row of columns per pair, so the fields keep A to E order when stacked on a phone
            for pair in (("A", "B"), ("C", "D"), ("E (optional)", None)):
                columns = st.columns(2)
                for column, name in zip(columns, pair):
                    if name:
                        options.append(column.text_input(f"Option {name}", key=f"try_{name[0].lower()}", max_chars=P.MAX_OPTION_CHARS))
                    else:
                        known = column.selectbox("Known correct option (optional)", ["", *P.LETTERS], key="try_known",
                                                 format_func=lambda x: x or "Not provided")
            run_col, load_col, _ = st.columns([1.2, 1, 2])
            run_col.form_submit_button("Run MIZAN Live", type="primary", width="stretch", key="btn_run", on_click=start_run, disabled=running or not has_key)
            load_col.form_submit_button("Load sample question", width="stretch", key="btn_load", disabled=running or not examples,
                                        on_click=load_example, args=(examples["examples"]["high_confidence"],) if examples else None)
        if running:
            try:
                state["live"] = run_live(question, options, known, docs["res"]["original"]["threshold"])
            finally:  # also when another click interrupts the run, so the button never stays disabled
                state["live_running"] = False
            st.rerun()
        live = state.get("live")
        if live and live.get("errors"):
            st.html('<ul class="mz-errors" role="alert">' + "".join(f"<li>{P.e(x)}</li>" for x in live["errors"]) + "</ul>")
        elif live and live.get("info"):
            st.html(f'<p class="mz-info" role="status">{P.e(live["info"])}</p>')
        elif live:
            st.html(P.live_result(live))
        st.html('<p class="mz-try-notes" style="font-size:.84rem">Your text is sent to OpenAI when you run it. The threshold was set on multiple-choice exam questions, so other kinds of text are outside what was measured.</p>')


def main() -> None:
    st.set_page_config(page_title="MIZAN", page_icon=str(P.LOGO), layout="wide", initial_sidebar_state="collapsed")
    live = live_lab_enabled()
    docs = load_documents(source_version(), live)
    st.html(docs["css"])
    st.html(docs["header"])
    components.html(docs["page"], height=PAGE_HEIGHT, scrolling=False)
    if live:  # stays out of the main flow until the owner approves it
        live_section(docs)


main()
