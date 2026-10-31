"""OFFLINE: writes exports/ for the deck and the video. No model is called.

    python scripts/export_assets.py numbers      # exports/deck_numbers.json only
    python scripts/export_assets.py              # also the screenshots and the chart

The screenshots need a running server on port 8501, the installed Chrome, and `pip install playwright`.
Playwright is only needed here, so it is not in requirements.txt.
"""
import json
import re
import sys

import _common  # noqa: F401
import yaml

from mizan import page as P, story as S
from mizan.config import ROOT

EXPORTS = ROOT / "exports"
SHOTS = EXPORTS / "screenshots"
URL = "http://localhost:8501"
VIEW = {"width": 1920, "height": 1080}
RESULTS, EXAMPLES, PRICES, TESTS = "artifacts/heldout_results.json", "artifacts/demo_examples.json", "config/prices.yaml", "artifacts/test_summary.txt"


def entry(name: str, display: str, source: str, key: str, value, derivation: str = "") -> dict:
    out = {"name": name, "display": display, "value": value, "source_file": source, "key": key}
    if derivation:
        out["derivation"] = derivation
    return out


def resolve(data, key: str):
    """Reads a dotted key such as a.b[0].c. A key may itself hold a dot, as in gpt-4.1."""
    parts = key.split(".")
    while parts:
        for size in range(len(parts), 0, -1):
            match = re.fullmatch(r"(.+?)((?:\[\d+\])*)", ".".join(parts[:size]))
            if match.group(1) in data:
                data = data[match.group(1)]
                for index in re.findall(r"\[(\d+)\]", match.group(2)):
                    data = data[int(index)]
                parts = parts[size:]
                break
        else:
            raise KeyError(key)
    return data


def deck_numbers(res: dict, examples: dict) -> list[dict]:
    o, s = res["original"], res["perturbation"]
    m = o["mechanism"]
    rows = []

    def add(name, display, key, derivation=""):
        rows.append(entry(name, display, RESULTS, key, resolve(res, key), derivation))

    def add_ci(name, key, fmt):
        low, high = resolve(res, key)
        rows.append(entry(name, fmt(low, high), RESULTS, key, [low, high]))

    points = lambda a, b: f"[{a * 100:+.1f}, {b * 100:+.1f}]"  # noqa: E731
    percent = lambda a, b: f"[{a * 100:.2f}%, {b * 100:.2f}%]"  # noqa: E731
    raw = lambda a, b: f"[{a:.4f}, {b:.4f}]"  # noqa: E731

    add("Lower measured inference cost, headline", f"{o['mizan']['saving_vs_top'] * 100:.0f}%", "original.mizan.saving_vs_top")
    add("Lower measured inference cost, exact", f"{o['mizan']['saving_vs_top'] * 100:.2f}%", "original.mizan.saving_vs_top")
    add_ci("Saving 95% CI", "original.mizan.saving_ci95", percent)
    add("Accuracy points vs always-economical", f"{o['non_dominance']['paired'][S.SMALL]['accuracy_diff']['observed'] * 100:+.1f}", f"original.non_dominance.paired.{S.SMALL}.accuracy_diff.observed")
    add_ci("Accuracy points vs always-economical 95% CI", f"original.non_dominance.paired.{S.SMALL}.accuracy_diff.ci95", points)
    add("MIZAN accuracy", f"{o['mizan']['accuracy'] * 100:.1f}%", "original.mizan.accuracy")
    add_ci("MIZAN accuracy 95% CI", "original.mizan.accuracy_ci95", percent)
    add("Always-large accuracy", f"{o['singles'][S.LARGE]['accuracy'] * 100:.1f}%", f"original.singles.{S.LARGE}.accuracy")
    add_ci("Always-large accuracy 95% CI", f"original.singles.{S.LARGE}.accuracy_ci95", percent)
    add("Always-economical accuracy", f"{o['singles'][S.SMALL]['accuracy'] * 100:.1f}%", f"original.singles.{S.SMALL}.accuracy")
    add("Mid-size accuracy", f"{o['singles'][S.MID]['accuracy'] * 100:.1f}%", f"original.singles.{S.MID}.accuracy")
    add("Matched random accuracy", f"{o['random']['accuracy_mean'] * 100:.1f}%", "original.random.accuracy_mean")
    add("Points below always-large", f"{abs(o['non_dominance']['paired'][S.LARGE]['accuracy_diff']['observed']) * 100:.1f}", f"original.non_dominance.paired.{S.LARGE}.accuracy_diff.observed", "absolute value")
    add_ci("Difference from always-large 95% CI", f"original.non_dominance.paired.{S.LARGE}.accuracy_diff.ci95", points)
    rows.append(entry("Fewer errors among accepted answers", f"{S.relative_error_reduction(res) * 100:.0f}%", RESULTS, "original.mechanism.random_acceptance_risk, original.mechanism.selective_risk",
                      S.relative_error_reduction(res), "(random_acceptance_risk - selective_risk) / random_acceptance_risk"))
    add("Error among accepted answers", f"{m['selective_risk'] * 100:.2f}%", "original.mechanism.selective_risk")
    add("Error under matched random acceptance", f"{m['random_acceptance_risk'] * 100:.2f}%", "original.mechanism.random_acceptance_risk")
    add("Accepted without escalation", f"{m['coverage'] * 100:.1f}%", "original.mechanism.coverage")
    add("Escalated", f"{o['mizan']['achieved_escalation'] * 100:.1f}%", "original.mizan.achieved_escalation")
    add("Held-out questions", str(o["n"]), "original.n")
    add("AUROC, original", f"{m['auroc']:.3f}", "original.mechanism.auroc")
    add_ci("AUROC, original, descriptive 95% CI", "original.mechanism.auroc_ci95_descriptive", raw)
    add("AUROC, option-shuffled", f"{s['mechanism']['auroc']:.3f}", "perturbation.mechanism.auroc")
    add_ci("AUROC, option-shuffled, descriptive 95% CI", "perturbation.mechanism.auroc_ci95_descriptive", raw)
    add("Frozen threshold", f"{o['threshold']:.2f}", "original.threshold")
    add("MIZAN vs matched random (directional, not conclusive)", f"{o['mizan_minus_random']['observed'] * 100:+.1f}", "original.mizan_minus_random.observed")
    add_ci("MIZAN vs matched random 95% CI", "original.mizan_minus_random.ci95", points)
    add("MIZAN vs mid-size", f"{o['non_dominance']['paired'][S.MID]['accuracy_diff']['observed'] * 100:+.1f}", f"original.non_dominance.paired.{S.MID}.accuracy_diff.observed")
    add_ci("MIZAN vs mid-size 95% CI", f"original.non_dominance.paired.{S.MID}.accuracy_diff.ci95", points)
    add("MIZAN cost, USD", f"${o['mizan']['total_cost_usd']:.5f}", "original.mizan.total_cost_usd")
    add("Always-large cost, USD", f"${o['singles'][S.LARGE]['total_cost_usd']:.5f}", f"original.singles.{S.LARGE}.total_cost_usd")
    add("Always-economical cost, USD", f"${o['singles'][S.SMALL]['total_cost_usd']:.5f}", f"original.singles.{S.SMALL}.total_cost_usd")
    add("Mid-size cost, USD", f"${o['singles'][S.MID]['total_cost_usd']:.5f}", f"original.singles.{S.MID}.total_cost_usd")
    add("Matched random cost, USD", f"${o['random']['total_cost_usd_mean']:.5f}", "original.random.total_cost_usd_mean")
    add("Preregistration commit", res["preflight"]["approved_commit"][:7], "preflight.approved_commit")
    add("Held-out run commit", res["preflight"]["head"][:7], "preflight.head")

    def demo(name, display, key):
        rows.append(entry(name, display, EXAMPLES, key, resolve(examples, key)))
    for label, role in (("Accept case", "high_confidence"), ("Escalate case", "lower_confidence")):
        ex = examples["examples"][role]
        base = f"examples.{role}"
        demo(f"{label}: ID", ex["id"], f"{base}.id")
        for i in (0, 1):
            p = ex["gpt_4o_mini"]["option_probabilities"][i]
            demo(f"{label}: economical model option {i + 1} letter", p["letter"], f"{base}.gpt_4o_mini.option_probabilities[{i}].letter")
            demo(f"{label}: economical model option {i + 1} probability", P.prob(p["probability"]), f"{base}.gpt_4o_mini.option_probabilities[{i}].probability")
        demo(f"{label}: economical model answer", ex["gpt_4o_mini"]["answer"], f"{base}.gpt_4o_mini.answer")
        demo(f"{label}: answer key", ex["correct_answer"], f"{base}.correct_answer")
        demo(f"{label}: route", ex["decision"], f"{base}.decision")
        demo(f"{label}: final answer", ex["final_answer"], f"{base}.final_answer")
        demo(f"{label}: final answer correct", "Correct" if ex["answered_correctly"] else "Incorrect", f"{base}.answered_correctly")
        if ex["gpt_4_1"]:
            demo(f"{label}: high-capability model answer", ex["gpt_4_1"]["answer"], f"{base}.gpt_4_1.answer")
            demo(f"{label}: high-capability model probability", P.prob(P.option_probability(ex["gpt_4_1"], ex["gpt_4_1"]["answer"])), f"{base}.gpt_4_1.option_probabilities[0].probability")

    prices = yaml.safe_load((ROOT / PRICES).read_text(encoding="utf-8"))
    rows.append(entry("Price date status: documented", str(prices["verified_on"]), PRICES, "verified_on", str(prices["verified_on"])))
    tests = S.test_summary()
    if tests:
        rows.append(entry("Automated tests passing", str(tests["count"]), TESTS, "count", tests["count"]))
    return rows


def write_numbers() -> None:
    EXPORTS.mkdir(exist_ok=True)
    rows = deck_numbers(S.load_json(S.RESULTS), S.load_json(S.EXAMPLES))
    (EXPORTS / "deck_numbers.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"-> exports/deck_numbers.json ({len(rows)} values)")


MEASURE = """(id) => {
  const f = document.querySelector('iframe'), d = f.contentDocument, el = d.getElementById(id);
  const main = document.querySelector('[data-testid=stMain]'), head = document.querySelector('.mz-head').getBoundingClientRect().height;
  const r = el.getBoundingClientRect();
  return { height: Math.round(r.height), available: Math.round(main.clientHeight - head), overflowX: d.documentElement.scrollWidth > d.documentElement.clientWidth };
}"""
TEXT = "(id) => document.querySelector('iframe').contentDocument.getElementById(id).innerText"


def write_screens() -> None:
    from playwright.sync_api import sync_playwright

    SHOTS.mkdir(parents=True, exist_ok=True)
    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_context(viewport=VIEW).new_page()
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(3000)
        frame = next(f for f in page.frames if f.query_selector("#overview"))

        def shot(name, section, wait=2200, click=None):
            page.evaluate("(id) => document.__mizanGo(id)", section)
            page.wait_for_timeout(1200)
            if click:
                frame.click(click)
            page.mouse.move(1900, 1070)  # so no card shows a hover state
            page.wait_for_timeout(wait)
            page.screenshot(path=str(SHOTS / f"{name}.png"))
            size = page.evaluate(MEASURE, section)
            text = page.evaluate(TEXT, section)
            print(name, size)
            if size["height"] > size["available"] or size["overflowX"]:
                problems.append(f"{name}: {size}")
            if re.search(r"(^|\s)0%(\s|$)|\[N\]", text):
                problems.append(f"{name}: placeholder or 0% in the text")

        shot("hero", "overview")
        shot("problem_scale", "problem")
        shot("demo_accept", "demo")
        shot("demo_escalate", "demo", click="#tab-low")
        shot("results_chart", "results")
        shot("accepted_errors", "accepted-errors")
        shot("robustness", "robustness")
        shot("impact_humain", "impact")
        shot("replay_done", "replay", wait=9500)

        figure = frame.evaluate("() => { const c = document.getElementById('chart'); return { data: c.data, layout: c.layout }; }")
        alone = browser.new_context(viewport={"width": 1600, "height": 900}).new_page()
        alone.goto(f"{URL}/app/static/fonts/LICENSE-inter.txt")
        faces = (P.WEB / "components.css").read_text(encoding="utf-8")
        faces = "\n".join(line for line in faces.splitlines() if line.startswith("@font-face")).replace("url('app/", "url('/app/")
        alone.set_content(f'<!doctype html><style>{faces} html,body{{margin:0;background:#0B2E30}}</style><div id="c" style="width:1600px;height:900px"></div>')
        alone.add_script_tag(path=str(P.PLOTLY))
        alone.evaluate("""async (fig) => {
          await document.fonts.load("600 13px Inter");
          const big = (a) => Object.assign({}, a, { font: Object.assign({}, a.font, { size: a.font.size * 1.5 }), yshift: a.yshift * 1.45,
                                                    text: a.text.replace('font-size:11px', 'font-size:16px') });
          const axis = (ax) => Object.assign({}, ax, { tickfont: { size: 17 }, title: Object.assign({}, ax.title, { font: { size: 19 } }) });
          fig.data.forEach((t) => { t.marker.size = t.marker.size * 1.3; });
          const layout = Object.assign({}, fig.layout, { width: 1600, height: 900, paper_bgcolor: '#0B2E30', plot_bgcolor: '#0B2E30', margin: { l: 100, r: 50, t: 40, b: 90 },
                                                         annotations: fig.layout.annotations.map(big), xaxis: axis(fig.layout.xaxis), yaxis: axis(fig.layout.yaxis) });
          await Plotly.newPlot('c', fig.data, layout, { displayModeBar: false, staticPlot: true });
        }""", figure)
        alone.wait_for_timeout(500)
        alone.screenshot(path=str(EXPORTS / "chart_results.png"), clip={"x": 0, "y": 0, "width": 1600, "height": 900})
        browser.close()
    print("-> exports/screenshots, exports/chart_results.png")
    if problems:
        raise SystemExit("Export problems:\n" + "\n".join(problems))


def main() -> None:
    write_numbers()
    if sys.argv[1:] != ["numbers"]:
        write_screens()


if __name__ == "__main__":
    main()
