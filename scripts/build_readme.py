"""OFFLINE: writes README.md. Every result in it is read from artifacts/heldout_results.json.

    python scripts/build_readme.py
"""
import _common  # noqa: F401

from mizan import page as P, story as S
from mizan.config import ROOT


def pct(x, places=2):
    return f"{x * 100:.{places}f}%"


def ci(c, places=2):
    return f"[{c[0] * 100:.{places}f}%, {c[1] * 100:.{places}f}%]"


def ci_pts(c, places=1):
    return f"[{c[0] * 100:+.{places}f}, {c[1] * 100:+.{places}f}]"


def render(res: dict) -> str:
    S.verify_approved_values(res)
    o, s, c, ops, pre = res["original"], res["perturbation"], res["comparison"], res["operations"], res["preflight"]
    h = S.hero_copy(res)
    impact, basis = S.impact_copy(res)
    m, sm = o["mechanism"], s["mechanism"]
    rows = [f"| Always {k} | {pct(v['accuracy'], 1)} | {ci(v['accuracy_ci95'], 1)} | ${v['total_cost_usd']:.5f} | {pct(v['saving_vs_top'], 1)} |" for k, v in o["singles"].items()]
    rows.append(f"| Matched Random (mean of {o['random']['seeds']} seeds) | {pct(o['random']['accuracy_mean'], 1)} | seed range {ci(o['random']['accuracy_range95'], 1)} | "
                f"${o['random']['total_cost_usd_mean']:.5f} | {pct(1 - o['random']['total_cost_usd_mean'] / o['singles'][S.LARGE]['total_cost_usd'], 1)} |")
    rows.append(f"| **Mizan** | **{pct(o['mizan']['accuracy'], 1)}** | {ci(o['mizan']['accuracy_ci95'], 1)} | **${o['mizan']['total_cost_usd']:.5f}** | **{pct(o['mizan']['saving_vs_top'])}** {ci(o['mizan']['saving_ci95'], 1)} |")
    table = "\n".join(rows)
    robust = "\n".join(f"| {r['metric']} | {r['original']} | {r['shuffled']} |" for r in S.robustness_rows(res))
    paired = "\n".join(f"| Always {k} | {b['accuracy_diff']['observed'] * 100:+.1f} | {ci_pts(b['accuracy_diff']['ci95'])} | {b['cost_diff']['observed']:+.5f} |" for k, b in o["non_dominance"]["paired"].items())
    mini = o["non_dominance"]["paired"][S.MID]
    snaps = ", ".join(next(iter(v)) for v in res["snapshots"]["original"].values())
    return f"""# MIZAN: Adaptive Arabic AI Routing

**{h['headline']}**

{h['subheadline']}

**{h['metric_value']} lower measured inference cost.** {h['evaluation']} {h['tradeoff']}

HUMAIN Hackathon, Challenge 2: *Deliver AI with Less Compute*.

Repository: [{P.github_url()}]({P.github_url()})

## The problem

Sending every Arabic request to the strongest available model is the safe default, and the expensive one. Many requests do not need it, but an application cannot tell which ones without some signal. A trained router or an AI judge on every answer adds cost of its own.

## How it works

```
Arabic application -> MIZAN -> Economical model -> Confidence gate -> Stronger model when needed
```

1. `gpt-4o-mini` answers the question first.
2. MIZAN reads the margin from that answer's own token log-probabilities: the log-probability of the chosen letter minus that of the best other valid letter.
3. If the margin is at least the frozen threshold ({o['threshold']!r}) and the output is exactly one valid letter, the answer stands.
4. Otherwise the request goes to `gpt-4.1`, and it pays for both calls.

There is no trained router, no AI judge and no fine-tuning. The scope is closed-answer multiple-choice questions, where correctness is objective.

## Results

Generated from [`artifacts/heldout_results.json`](artifacts/heldout_results.json) by `scripts/build_readme.py`.

{o['n']} held-out questions, one run per model, threshold and prompt frozen before the run ([preregistration](docs/decisions.md)).

| Strategy | Accuracy | 95% CI | Total cost | Saving vs Always gpt-4.1 |
|---|---|---|---|---|
{table}

- **{h['proofs'][0]}** (95% CI {ci_pts(o['non_dominance']['paired'][S.SMALL]['accuracy_diff']['ci95'])}).
- **{h['proofs'][1]}:** {pct(m['selective_risk'])} vs {pct(m['random_acceptance_risk'])} error at the same {pct(m['coverage'], 1)} acceptance.
- **The trade-off:** Mizan is {abs(o['non_dominance']['paired'][S.LARGE]['accuracy_diff']['observed']) * 100:.1f} points below Always gpt-4.1 (95% CI {ci_pts(o['non_dominance']['paired'][S.LARGE]['accuracy_diff']['ci95'])}).
- **Against matched Random:** {S.directional_copy(res)}, directional, not conclusive. The preregistered primary result is "{o['primary']}", and the overall decision is "{res['decision']}"

### Robustness: the same questions with the options reordered

| | Original | Option-shuffled |
|---|---|---|
{robust}

Confidence quality remained stable after the options moved. Option order changed {c['routing_decisions_changed']} of {o['n']} routing decisions. This is a perturbation of the same questions, not a new test set.

### Impact at scale

{impact} {basis}

## Run the demo

Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

It works without an API key: the two examples show a run labelled "Recorded run", and the replay and evidence sections use recorded results. To enable live calls, copy `.env.example` to `.env` and add your own `OPENAI_API_KEY`. Each press of "Route with MIZAN" then makes a real, paid call with the frozen prompt, settings and threshold. The two examples always show the recorded run. Live spend goes to a separate local ledger, `artifacts/demo_ledger.jsonl`, and stops at ${_reserve():.2f}.

## Recompute offline

No API key, no paid call and no question text needed:

```bash
pip install -r requirements.txt
python scripts/recompute_offline.py
python -m pytest -q
```

`recompute_offline.py` runs the evaluation's analysis code on [`artifacts/heldout_per_item.json`](artifacts/heldout_per_item.json), the per-item outcomes, and compares every number under `original`, `perturbation` and `comparison` with the results file. It writes nothing.

The raw API responses are not in this repository. `scripts/analyze_heldout.py` needs them and is bound to the run commit, so it refuses to run on later commits.

## Technical details and limitations

- **The split.** {S.SPLIT_SENTENCE} Development and held-out data share none of the 40 subject-by-level groups, though 7 subjects appear on both sides at different levels. Results describe the 25 held-out groups, equally weighted, not ArabicMMLU as a whole. Development and held-out numbers are not comparable samples. See [`artifacts/heldout_report.md`](artifacts/heldout_report.md), section 4.
- **The split code.** `stratified_split` had a bug that kept each group entirely on one side. It is fixed for future use, but no data or result was regenerated. All reported results use the original split, listed in [`artifacts/split_ids.json`](artifacts/split_ids.json). `scripts/prepare_data.py` rebuilds that split by default.
- **gpt-4.1-mini.** Always gpt-4.1-mini costs less than Mizan (${o['singles'][S.MID]['total_cost_usd']:.5f} vs ${o['mizan']['total_cost_usd']:.5f}). Mizan is {mini['accuracy_diff']['observed'] * 100:+.1f} points {ci_pts(mini['accuracy_diff']['ci95'])} on accuracy, an interval that includes zero, so Mizan is not shown to be more accurate than it.
- **Paired comparisons, original run:**

  | Mizan minus | Accuracy (points) | 95% CI | Cost (USD) |
  |---|---|---|---|
{_indent(paired)}

- **Confidence signal.** Margin AUROC for gpt-4o-mini correctness: {m['auroc']:.4f} original, {sm['auroc']:.4f} option-shuffled (descriptive intervals in the results file).
- **Threshold.** Set on development data, for which the target escalation was {pct(pre['target_rate'], 0)}. It escalated {pct(o['mizan']['achieved_escalation'], 1)} on held-out data, and the target was not enforced there. The criterion used to select it was chosen after development results had been seen, so development numbers are not evidence.
- **Scope of the projection.** The one-million figure assumes tasks like these exam questions. Other kinds of text were not measured.
- **Latency** is not a reported result. Recorded times include connection stalls and should not be read as model speed.
- **Models:** {snaps}. Prices are the Standard tier, verified on {pre['prices_verified_on']}. Total recorded experiment cost: ${ops['ledger_total']:.5f}.
- **Commits:** preregistration `{pre['approved_commit'][:7]}`, run `{pre['head'][:7]}`.
- **Demo examples** are chosen by a fixed rule, written in `src/mizan/demo.py`, not picked by hand. The high-confidence example excludes religious subjects, a presentation choice with no effect on any result. Their English translations were made by Claude (AI) and were not reviewed by a professional translator.

The full decision log and preregistration are in [`docs/decisions.md`](docs/decisions.md).

## License

The code in this repository is under the [MIT License](LICENSE). That license covers the code only. The dataset keeps its own license, described below.

## Data source and license

[ArabicMMLU](https://github.com/mbzuai-nlp/ArabicMMLU) (Koto et al., *ArabicMMLU: Assessing Massive Multitask Language Understanding in Arabic*, Findings of ACL 2024), 14,455 rows as downloaded from [Hugging Face](https://huggingface.co/datasets/MBZUAI/ArabicMMLU).

The two sources state different licenses: the GitHub repository says CC BY-NC-SA 4.0 and the Hugging Face card says CC BY-NC 4.0. This repository follows the stricter one for dataset content.

- Tracked with attribution, under CC BY-NC-SA 4.0, for non-commercial use: the text of the two demo questions in `artifacts/demo_examples.json`, and their translations in `artifacts/demo_translations.json` and `artifacts/demo_examples.json`.
- Not tracked: all other question text, the processed splits and the raw API responses. The other artifacts hold item IDs and outcomes only.
"""


def _indent(text: str) -> str:
    return "\n".join("  " + line for line in text.splitlines())


def _reserve() -> float:
    from mizan.config import experiment
    return experiment()["budget"]["reserve_usd"]


def main():
    (ROOT / "README.md").write_text(render(S.load_json(S.RESULTS)), encoding="utf-8", newline="\n")
    print("-> README.md")


if __name__ == "__main__":
    main()
