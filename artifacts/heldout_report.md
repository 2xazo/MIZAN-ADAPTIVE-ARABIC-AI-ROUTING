# MIZAN held-out report

Generated: 2026-10-30T21:27:46+0300. All numbers come from `artifacts/heldout_results.json`.

**Decision: Conditional GO with limited claims.** The gain over matched random is an inconclusive trend, not a success.

## 1. Original held-out

N = 500. Margin threshold 6.249999994711611 (`margin < threshold` escalates).

| Strategy | Accuracy | 95% CI | Total cost | Saving vs Always gpt-4.1 | Invalid outputs |
|---|---|---|---|---|---|
| Always gpt-4o-mini | 73.60% | [69.19%, 77.40%] | $0.00694 | 92.50% | 0 |
| Always gpt-4.1-mini | 76.00% | [72.20%, 79.40%] | $0.01851 | 80.00% | 0 |
| Always gpt-4.1 | 82.60% | [79.40%, 85.80%] | $0.09254 | 0.00% | 0 |
| **Mizan** | **79.00%** | [75.40%, 82.41%] | $0.03104 | 66.45% (CI [62.44%, 70.48%]) | 0 (small model) |
| Matched Random (mean of 1000 seeds) | 75.90% | seed range [74.20%, 77.60%] | $0.03045 | 67.10% | same as Mizan |

- **Mizan minus Random: +3.10 points, 95% CI [-0.20, +6.00]. Primary result: Inconclusive trend.**
- Margin AUROC for gpt-4o-mini correctness: 0.8214 (descriptive 95% CI [0.7828, 0.8604]).
- Escalation: target on Dev 30.00%, achieved 25.40% (127 of 500). The target is not enforced on this set.
- `not_available` margins (scored +inf, never escalated by margin): 1.
- Selective risk / coverage: coverage 74.60%; risk on accepted items 15.82% (accuracy 84.18%), vs random acceptance risk 26.40% (accuracy 73.60%).
- gpt-4o-mini error rate inside the escalated set: 57.48%.

Non-dominance: dominated by no single model; on the observed frontier of the four measured points: yes.

| Mizan minus | Accuracy (points) | 95% CI | Cost (USD) | 95% CI |
|---|---|---|---|---|
| Always gpt-4o-mini | +5.40 | [+2.60, +8.41] | +0.02410 | [+0.02023, +0.02783] |
| Always gpt-4.1-mini | +3.00 | [-0.20, +6.40] | +0.01254 | [+0.00877, +0.01626] |
| Always gpt-4.1 | -3.60 | [-6.00, -1.40] | -0.06150 | [-0.06543, -0.05761] |

Education level slices (descriptive only, no claim):

| Level | N | Mizan accuracy | 95% CI | Escalation | Cost | Warning |
|---|---|---|---|---|---|---|
| High | 80 | 63.75% | [53.75%, 72.50%] | 32.50% | $0.00648 |  |
| Middle | 140 | 80.00% | [73.57%, 86.43%] | 26.43% | $0.00848 |  |
| None | 80 | 81.25% | [72.50%, 88.75%] | 27.50% | $0.00545 |  |
| Primary | 140 | 85.71% | [79.29%, 91.43%] | 20.71% | $0.00635 |  |
| Prof | 20 | 75.00% | [50.00%, 90.12%] | 45.00% | $0.00238 | small slice (N < 30) |
| Univ | 40 | 80.00% | [67.50%, 92.50%] | 10.00% | $0.00190 |  |

## 2. Option-order perturbation

This is not a new held-out set, unseen questions or out-of-domain data. It is the same 500 questions with options reordered.
Seed 20261030. Items whose displayed order stayed identical: 0. Items whose correct letter changed: 425.

N = 500. Margin threshold 6.249999994711611 (`margin < threshold` escalates).

| Strategy | Accuracy | 95% CI | Total cost | Saving vs Always gpt-4.1 | Invalid outputs |
|---|---|---|---|---|---|
| Always gpt-4o-mini | 73.80% | [70.00%, 77.80%] | $0.00694 | 92.50% | 0 |
| Always gpt-4.1-mini | 75.00% | [71.20%, 78.80%] | $0.01851 | 80.00% | 0 |
| Always gpt-4.1 | 80.00% | [76.40%, 83.60%] | $0.09254 | 0.00% | 0 |
| **Mizan** | **77.20%** | [73.40%, 81.00%] | $0.03039 | 67.17% (CI [63.12%, 71.13%]) | 0 (small model) |
| Matched Random (mean of 1000 seeds) | 75.32% | seed range [73.80%, 77.00%] | $0.03006 | 67.52% | same as Mizan |

- **Mizan minus Random: +1.88 points, 95% CI [-1.40, +5.20]. Primary result: Inconclusive trend.**
- Margin AUROC for gpt-4o-mini correctness: 0.8248 (descriptive 95% CI [0.7835, 0.8618]).
- Escalation: target on Dev 30.00%, achieved 25.00% (125 of 500). The target is not enforced on this set.
- `not_available` margins (scored +inf, never escalated by margin): 6.
- Selective risk / coverage: coverage 75.00%; risk on accepted items 14.67% (accuracy 85.33%), vs random acceptance risk 26.20% (accuracy 73.80%).
- gpt-4o-mini error rate inside the escalated set: 60.80%.

Non-dominance: dominated by no single model; on the observed frontier of the four measured points: yes.

| Mizan minus | Accuracy (points) | 95% CI | Cost (USD) | 95% CI |
|---|---|---|---|---|
| Always gpt-4o-mini | +3.40 | [+0.20, +6.80] | +0.02345 | [+0.01974, +0.02729] |
| Always gpt-4.1-mini | +2.20 | [-1.20, +5.40] | +0.01188 | [+0.00826, +0.01569] |
| Always gpt-4.1 | -2.80 | [-5.00, -0.60] | -0.06216 | [-0.06595, -0.05822] |

Education level slices (descriptive only, no claim):

| Level | N | Mizan accuracy | 95% CI | Escalation | Cost | Warning |
|---|---|---|---|---|---|---|
| High | 80 | 66.25% | [56.25%, 76.25%] | 32.50% | $0.00632 |  |
| Middle | 140 | 76.43% | [70.00%, 82.86%] | 21.43% | $0.00710 |  |
| None | 80 | 76.25% | [67.47%, 85.00%] | 22.50% | $0.00458 |  |
| Primary | 140 | 84.29% | [77.86%, 90.00%] | 25.71% | $0.00753 |  |
| Prof | 20 | 55.00% | [35.00%, 75.00%] | 45.00% | $0.00245 | small slice (N < 30) |
| Univ | 40 | 90.00% | [80.00%, 97.50%] | 15.00% | $0.00241 |  |

### Change, shuffled minus original

- AUROC: +0.0035 (descriptive 95% CI [-0.0328, +0.0428])
- Mizan accuracy: -1.80 points
- Escalation rate: -0.40 points
- Total cost: -0.00066 USD (-0.0000013 USD per item)
- Saving vs Always gpt-4.1: +0.71 points
- Routing decisions changed: 70 of 500 (34 newly escalated, 36 no longer escalated)

### Paired comparison by question ID

| Answerer | Same correctness | Right to wrong | Wrong to right |
|---|---|---|---|
| Mizan | 457 | 26 | 17 |
| Always gpt-4o-mini | 445 | 27 | 28 |
| Always gpt-4.1-mini | 451 | 27 | 22 |
| Always gpt-4.1 | 473 | 20 | 7 |

Routing score change: mean absolute 3.5989, median absolute 2.6250 over 494 items finite in both runs. Finite to infinite: 5. Infinite to finite: 0. Infinite in both: 1.

Items with an option referring to other options (flagged, never removed): 42. Mizan accuracy, original: flagged 80.95%, unflagged 78.82%. Shuffled: flagged 80.95%, unflagged 76.86%.

### Registered robustness claim

- AUROC_shuffled >= AUROC_original - 0.05: **holds** (0.8248 vs 0.8214).
- Mizan minus Random keeps the same sign: **holds** (+3.10 vs +1.88).

## 3. Integrity and operations

- Approved preregistration commit: `a34020c1e01758f9098cf529c5e7b615088805ba`
- Commit used for the run: `47ee70a0a02d5fec8d17711fc8beb6c7b2db6c24` (adds new files only; list below)
- Files added after the approved commit: `scripts/analyze_heldout.py`, `scripts/run_heldout.py`, `src/mizan/heldout.py`, `tests/test_heldout.py`
- `docs/decisions.md` SHA-256: `e10b267690d74b6c8aa776b7c74fba1c2fce42192e41e2296354bb4975d35dd8`, unchanged at the end: True
- Model snapshots returned: {'original': {'gpt-4o-mini': {'gpt-4o-mini-2024-07-18': 500}, 'gpt-4.1-mini': {'gpt-4.1-mini-2025-04-14': 500}, 'gpt-4.1': {'gpt-4.1-2025-04-14': 500}}, 'perturbation': {'gpt-4o-mini': {'gpt-4o-mini-2024-07-18': 500}, 'gpt-4.1-mini': {'gpt-4.1-mini-2025-04-14': 500}, 'gpt-4.1': {'gpt-4.1-2025-04-14': 500}}}
- API calls: 3000 succeeded of 3001 attempts ({'heldout/gpt-4o-mini': 500, 'heldout/gpt-4.1': 500, 'heldout/gpt-4.1-mini': 500, 'perturbation/gpt-4o-mini': 500, 'perturbation/gpt-4.1': 500, 'perturbation/gpt-4.1-mini': 500})
- Cache hits/misses: heldout/gpt-4o-mini (with gpt-4o-mini) hits 0 misses 500 from data\cache; heldout/gpt-4.1 (with gpt-4o-mini) hits 0 misses 500 from data\cache; heldout/gpt-4.1-mini (with gpt-4.1-mini) hits 0 misses 500 from data\cache; heldout/gpt-4.1 (with gpt-4.1-mini) hits 500 misses 0 from data\cache; perturbation/gpt-4o-mini (with gpt-4o-mini) hits 0 misses 500 from data\cache_option_order; perturbation/gpt-4.1 (with gpt-4o-mini) hits 0 misses 500 from data\cache_option_order; perturbation/gpt-4.1-mini (with gpt-4.1-mini) hits 0 misses 500 from data\cache_option_order; perturbation/gpt-4.1 (with gpt-4.1-mini) hits 500 misses 0 from data\cache_option_order
- Errors and retries: 1 failed attempts, {'TimeoutError:None': 1}. A failed attempt may be billed by the provider but is not in the ledger.
- Unique response IDs shared between the two runs: 0. Prompt-hash mismatches against the items: 0.
- Cost of this experiment: original $0.11799, perturbation $0.11799; ledger delta $0.23599
- Actual cumulative experiment cost: $0.36660 of $8.00
- Settings changed after held-out was opened: none. Tracked changes at the end: [' M artifacts/cost_ledger.jsonl', '?? artifacts/heldout_cache_log.jsonl', '?? artifacts/heldout_call_log.jsonl', '?? artifacts/heldout_preflight.json', '?? artifacts/perturbation_manifest.json'].

Differences from the preregistration text, all reported rather than silently applied:

- Section 12 places the analysis of the original run before the perturbation run. The coordinator's approval orders the analysis after both runs, and that order was followed. No held-out result was analyzed before the perturbation run finished.
- Section 12 requires the analysis script to be committed before step 1. That commit comes after the approved commit and adds new files only.
- Section 12 names `scripts/run_eval.py` directly. `scripts/run_heldout.py` calls its `main()` with exactly those arguments, adding attempt and cache logs.
- The optional held-out curve (section 9) was not computed, so no other operating point was ever visible.
- AUROC confidence intervals and the GO mapping in `src/mizan/heldout.py` were added by the executor before any held-out call. The intervals are descriptive.

## 4. Methodological finding for the coordinator's decision

Added by hand after the analysis. Nothing was fixed or re-run, and no result above changed.

**The Dev/Held-out split is not stratified as `docs/decisions.md` (decision 15) and the preregistration assume.**

- Dev and Held-out share 0 of 40 Subject x Level strata. Dev has 15 strata and Held-out has 25, with exactly 20 items in each.
- All 500 Held-out items are affected. 280 of them are in subjects that never appear in Dev, such as Islamic Studies and General Knowledge. Dev has no `Prof` items.
- Likely cause, from reading `stratified_split` in `src/mizan/data.py`: items are dealt round-robin across 40 strata, then assigned to splits with a pattern that repeats every 8 items. Since 40 is a multiple of 8, each stratum always lands in the same split. The observed counts fit this; the mechanism was not tested separately.
- Items are drawn equally per stratum (20 each), so the sample is not proportional to ArabicMMLU's 14,455 rows.

What this does and does not affect:

- Still sound: Held-out was unseen, the threshold was frozen first, and every comparison is paired on the same 500 items. No Dev information leaked. The test is, if anything, harder than a same-strata test.
- Limited: results describe these 25 strata, equally weighted, not ArabicMMLU as a whole. Dev and Held-out are not comparable samples, so Dev-to-Held-out changes (30% to 25.4% escalation, for example) cannot be read as sampling noise or as drift.
- A corrected split would use new items and a new Dev, which is a new experiment. It was not attempted.

Other limits on claims:

- The GO mapping was written by the executor before any held-out call. It was not part of the preregistration.
- Non-dominance holds on point estimates only. Against Always gpt-4.1-mini, Mizan's accuracy gain has a CI that includes zero, and it costs significantly more.

## 5. Decision

**Conditional GO with limited claims.** The gain over matched random is an inconclusive trend, not a success. The split finding in section 4 further limits claims to these 25 strata, and whether it changes this decision is the coordinator's call.
