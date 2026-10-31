# MIZAN: Adaptive Arabic AI Routing

**Does every Arabic task need the biggest model?**

MIZAN lets an economical model answer first, and pays for the stronger model only when the answer itself shows doubt.

**66% lower measured inference cost.** Tested on 500 held-out Arabic questions not used during development. MIZAN achieved 79.0% accuracy, compared with 82.6% for always using gpt-4.1.

HUMAIN Hackathon, Challenge 2: *Deliver AI with Less Compute*.

Repository: [https://github.com/2xazo/MIZAN-ADAPTIVE-ARABIC-AI-ROUTING](https://github.com/2xazo/MIZAN-ADAPTIVE-ARABIC-AI-ROUTING)

Built and submitted individually by Abdulaziz Alothman. AI-assisted development tools were used during implementation; all product decisions, evaluation design, validation, and final submission are owned by the author.

## The problem

Sending every Arabic request to the strongest available model is the safe default, and the expensive one. Many requests do not need it, but an application cannot tell which ones without some signal. A trained router or an AI judge on every answer adds cost of its own.

## How it works

```
Arabic application -> MIZAN -> Economical model -> Confidence gate -> Stronger model when needed
```

1. `gpt-4o-mini` answers the question first.
2. MIZAN reads the margin from that answer's own token log-probabilities: the log-probability of the chosen letter minus that of the best other valid letter.
3. If the margin is at least the frozen threshold (6.249999994711611) and the output is exactly one valid letter, the answer stands.
4. Otherwise the request goes to `gpt-4.1`, and it pays for both calls.

There is no trained router, no AI judge and no fine-tuning. The scope is closed-answer multiple-choice questions, where correctness is objective.

## Results

Generated from [`artifacts/heldout_results.json`](artifacts/heldout_results.json) by `scripts/build_readme.py`.

500 held-out questions, one run per model, threshold and prompt frozen before the run ([preregistration](docs/decisions.md)).

| Strategy | Accuracy | 95% CI | Total cost | Saving vs Always gpt-4.1 |
|---|---|---|---|---|
| Always gpt-4o-mini | 73.6% | [69.2%, 77.4%] | $0.00694 | 92.5% |
| Always gpt-4.1-mini | 76.0% | [72.2%, 79.4%] | $0.01851 | 80.0% |
| Always gpt-4.1 | 82.6% | [79.4%, 85.8%] | $0.09254 | 0.0% |
| Matched Random (mean of 1000 seeds) | 75.9% | seed range [74.2%, 77.6%] | $0.03045 | 67.1% |
| **Mizan** | **79.0%** | [75.4%, 82.4%] | **$0.03104** | **66.45%** [62.4%, 70.5%] |

- **+5.4 accuracy points vs always using the economical model** (95% CI [+2.6, +8.4]).
- **40% fewer errors among accepted answers than matched random acceptance:** 15.82% vs 26.40% error at the same 74.6% acceptance.
- **The trade-off:** Mizan is 3.6 points below Always gpt-4.1 (95% CI [-6.0, -1.4]).
- **Against matched Random:** +3.1 pts [-0.2, +6.0], directional, not conclusive. The preregistered primary result is "Inconclusive trend", and the overall decision is "Conditional GO with limited claims."

### Robustness: the same questions with the options reordered

| | Original | Option-shuffled |
|---|---|---|
| Accuracy | 79.0% | 77.2% |
| AUROC | 0.8214 | 0.8248 |
| Handled share | 74.6% | 75.0% |
| Saving | 66.45% | 67.17% |

Confidence quality remained stable after the options moved. Option order changed 70 of 500 routing decisions. This is a perturbation of the same questions, not a new test set.

### Impact at scale

Projected at one million similar tasks: approximately 746,000 handled without a high-capability model call. Projected from the 74.6% economical-model acceptance rate measured on held-out data.

## Run the demo

Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

It works without an API key: the two examples show a run labelled "Recorded run", and the replay and evidence sections use recorded results. The live form is hidden by default. To enable it, set `MIZAN_LIVE_LAB=1`, copy `.env.example` to `.env`, and add your own `OPENAI_API_KEY`. The form then opens from the "Try your own question — Live" button in the Demo section, and each press of "Run MIZAN Live" makes a real, paid call with the frozen prompt, settings and threshold. The two examples always show the recorded run. Live spend goes to a separate local ledger, `artifacts/demo_ledger.jsonl`, and stops at $2.00.

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

- **The split.** The realized evaluation split was subject-by-level disjoint; the exact manifest was preserved, and the splitter was fixed with a regression test. Development and held-out data share none of the 40 subject-by-level groups, though 7 subjects appear on both sides at different levels. Results describe the 25 held-out groups, equally weighted, not ArabicMMLU as a whole. Development and held-out numbers are not comparable samples. See [`artifacts/heldout_report.md`](artifacts/heldout_report.md), section 4.
- **The split code.** `stratified_split` had a bug that kept each group entirely on one side. It is fixed for future use, but no data or result was regenerated. All reported results use the original split, listed in [`artifacts/split_ids.json`](artifacts/split_ids.json). `scripts/prepare_data.py` rebuilds that split by default.
- **gpt-4.1-mini.** Always gpt-4.1-mini costs less than Mizan ($0.01851 vs $0.03104). Mizan is +3.0 points [-0.2, +6.4] on accuracy, an interval that includes zero, so Mizan is not shown to be more accurate than it.
- **Paired comparisons, original run:**

  | Mizan minus | Accuracy (points) | 95% CI | Cost (USD) |
  |---|---|---|---|
  | Always gpt-4o-mini | +5.4 | [+2.6, +8.4] | +0.02410 |
  | Always gpt-4.1-mini | +3.0 | [-0.2, +6.4] | +0.01254 |
  | Always gpt-4.1 | -3.6 | [-6.0, -1.4] | -0.06150 |

- **Confidence signal.** Margin AUROC for gpt-4o-mini correctness: 0.8214 original, 0.8248 option-shuffled (descriptive intervals in the results file).
- **Threshold.** Set on development data, for which the target escalation was 30%. It escalated 25.4% on held-out data, and the target was not enforced there. The criterion used to select it was chosen after development results had been seen, so development numbers are not evidence.
- **Scope of the projection.** The one-million figure assumes tasks like these exam questions. Other kinds of text were not measured.
- **Latency** is not a reported result. Recorded times include connection stalls and should not be read as model speed.
- **Models:** gpt-4o-mini-2024-07-18, gpt-4.1-mini-2025-04-14, gpt-4.1-2025-04-14. Prices are the Standard tier, verified on 2026-10-30. Total recorded experiment cost: $0.36660.
- **Commits:** preregistration `a34020c`, run `47ee70a`.
- **Demo examples** are chosen by a fixed rule, written in `src/mizan/demo.py`, not picked by hand. The high-confidence example excludes religious subjects, a presentation choice with no effect on any result. Their English translations were made by Claude (AI) and were not reviewed by a professional translator.

The full decision log and preregistration are in [`docs/decisions.md`](docs/decisions.md).

## License

The code in this repository is under the [MIT License](LICENSE). That license covers the code only. The dataset keeps its own license, described below.

## Data source and license

[ArabicMMLU](https://github.com/mbzuai-nlp/ArabicMMLU) (Koto et al., *ArabicMMLU: Assessing Massive Multitask Language Understanding in Arabic*, Findings of ACL 2024), 14,455 rows as downloaded from [Hugging Face](https://huggingface.co/datasets/MBZUAI/ArabicMMLU).

The two sources state different licenses: the GitHub repository says CC BY-NC-SA 4.0 and the Hugging Face card says CC BY-NC 4.0. This repository follows the stricter one for dataset content.

- Tracked with attribution, under CC BY-NC-SA 4.0, for non-commercial use: the text of the two demo questions in `artifacts/demo_examples.json`, and their translations in `artifacts/demo_translations.json` and `artifacts/demo_examples.json`.
- Not tracked: all other question text, the processed splits and the raw API responses. The other artifacts hold item IDs and outcomes only.
