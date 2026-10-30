# MIZAN — Adaptive Arabic AI Routing

**The required AI quality, with less compute.**

HUMAIN Hackathon — Challenge 2: *Deliver AI with Less Compute*.

Most organizations send every request to their most expensive model to be safe. MIZAN sends each
Arabic request to an economical model first, reads that model's own confidence from its token
log-probabilities, and escalates to a stronger model **only** when the answer looks unreliable.

```
Arabic request ─► Economical model ─► Validity + confidence gate ─┬─► Accept (cheap)
                                                                  └─► Escalate ─► Stronger model
```

> **Status: Phase 1 (Go/No-Go).** No results are published yet. Every number in this repo will be
> generated from `artifacts/results.json`, never typed by hand.

## Design decisions (short version — full log in `docs/decisions.md`)

- **Closed-answer tasks only** (ArabicMMLU multiple choice). Their correctness is objective, and a cheap
  validity check exists. Open-ended generation is out of scope on purpose: verifying it cheaply is
  unreliable, and an LLM judge on every answer would eat the savings.
- **No trained router, no LLM judge, no fine-tuning.** The signal is the small model's own log-probability
  after it answers — free, and measurable with AUROC.
- **Strict validity:** the output must be exactly one allowed letter. Anything else is escalated.
- **Honest baselines:** Always-Small, Always-Large, Random routing at the *same* escalation rate
  (averaged over 1000 seeds), and an Oracle upper bound.
- **Dev / Held-out discipline:** model pair, confidence signal and threshold are chosen on Dev only.
  Held-out is locked in code until GO.

## Project layout

```
config/       experiment.yaml (seed, budget, call params, GO criteria), prices.yaml
src/mizan/    data, prompts, client (plain HTTPS), parsing, routing, metrics, analysis, costs
scripts/      prepare_data → probe_models → run_eval (paid) → analyze (offline)
tests/        unit + offline end-to-end tests (no network)
artifacts/    results.json (single source of truth), reports, split IDs, cost ledger
data/         processed splits and raw API responses (git-ignored)
```

## Run

Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # then put YOUR key in .env
python -m pytest -q                                      # offline tests

python scripts/prepare_data.py                           # ArabicMMLU -> stratified Dev/Held-out
python scripts/probe_models.py                           # what this account supports (tiny cost)
# verify prices in config/prices.yaml, set verified: true
python scripts/run_eval.py --small gpt-4.1-mini --large gpt-4.1 --n 5      # smoke test
python scripts/run_eval.py --small gpt-4.1-mini --large gpt-4.1 --n 100    # Go/No-Go
python scripts/analyze.py --pairs gpt-4.1-mini:gpt-4.1 --n 100             # offline
```

**Reproduce without an API key:** `scripts/analyze.py` recomputes every number from the cached raw
responses in `data/cache/`. No call is ever repeated: cached items are skipped and every spend is logged
to `artifacts/cost_ledger.jsonl` with a hard stop at the experiment budget.

## Data

[ArabicMMLU](https://github.com/mbzuai-nlp/ArabicMMLU) (MBZUAI) — multiple-choice questions from real
school exams across Arabic-speaking countries. Its license must be confirmed before any question text is
published; until then only item IDs (`artifacts/split_ids.json`) are tracked in git.
