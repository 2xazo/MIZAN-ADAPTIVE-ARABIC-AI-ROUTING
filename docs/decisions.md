# Decision log

| # | Decision | Why |
|---|---|---|
| 1 | Challenge 2, project MIZAN | Objectively measurable on held-out data; matches the judging criteria and HUMAIN's focus on inference efficiency and Arabic AI. |
| 2 | Closed-answer tasks only | Objective correctness and a free validity check. Open tasks would need an LLM judge that consumes the savings. |
| 3 | ArabicMMLU first; ArBanking77 only if obtainable in 20 min | ArabicMMLU is public and confirmed. The full ArBanking77 corpus is available on request only. |
| 4 | OpenAI, pair chosen by live probe | Must return logprobs + usage. `gpt-4.1-nano` was shut down on 2026-10-23; reasoning models do not return logprobs. Candidates: small = gpt-4.1-mini, gpt-4o-mini, gpt-5.4-nano, gpt-5.6-luna; large = gpt-4.1. |
| 5 | Plain HTTPS client, no SDK | Every parameter sent is explicit and recorded; raw responses cached for offline replay. |
| 6 | No structured outputs / json_schema | Can return empty logprobs. Format is enforced by prompt and checked in code. |
| 7 | Strict validity = whole output is exactly one allowed letter | Lenient parsing would inflate the small model's accuracy. Invalid output = automatic escalation, counted in escalation rate. |
| 8 | Answer token = first non-whitespace token | Models may emit a leading space/newline token. |
| 9 | Signals: raw chosen logprob (primary), normalized (only if all options visible in top-20), margin (`not_available` if no competitor) | Normalizing over a partial top-k inflates confidence. Choice of signal is part of Dev tuning, frozen before Held-out. |
| 10 | Margin `not_available` scored as maximum confidence for routing | No valid competitor in the top-20 means the competitor's mass is below the 20th token. |
| 11 | Random baseline: same escalation count, invalid outputs always escalated, 1000 seeds | Isolates the value of the confidence signal itself. |
| 12 | Oracle: escalate only if small wrong AND large right | Upper bound; uses ground truth, not deployable. |
| 13 | Operating point: max saving subject to ≤ 2 points loss vs Always-Large, on Dev | Agreed GO criterion. Dev estimate is optimistic; Held-out is the real number. |
| 14 | Cost = input/1M × input price + output/1M × output price; reasoning tokens included in output | Official per-token billing. Prices must be verified and frozen before paid runs. |
| 15 | Stratified split by Subject × Level, seed 42 | Held-out covers every level, enabling the robustness slice without re-splitting. |
| 16 | Budget: $8 experiments (hard stop in code), $2 reserve | Owner's cap. |
| 17 | Temperature 0, no few-shot, same prompt for both models | Fair, deterministic comparison. |

## Log

- 2026-10-30: Phase 1 code complete; 25 offline tests passing. Awaiting live probe and data download on the owner's machine (the build sandbox has no access to Hugging Face or the OpenAI API).
- 2026-10-30: Data prepared: 14455 raw rows, 14455 valid, 0 rejected; Answer Key is already A-E, so `normalize_row` is unchanged. Dev 300, Held-out 500.
- 2026-10-30: Probe passed with logprobs and top_logprobs=20: gpt-4.1-mini, gpt-4o-mini, gpt-4.1. gpt-5.4-nano and gpt-5.6-luna were rejected because they allow top_logprobs of at most 5 (the config asks for 20); they were not retried, to keep scope and config fixed.
- 2026-10-30: `config/prices.yaml`: source URL updated to the page OpenAI now redirects to; official Standard prices match the existing values. `verified` stays false pending owner approval.
- 2026-10-30: Owner approved the prices: `verified: true`, `verified_on: 2026-10-30`.
- 2026-10-30: The Hugging Face dataset has 14,455 rows; the paper reports 14,575. We use the 14,455 rows as downloaded.
- 2026-10-30: gpt-5.4-nano and gpt-5.6-luna were rejected only because they cap top_logprobs at 5. They were not tested further (out of scope).
- 2026-10-30: Bug fix: `analyze.py` crashed writing results.json because YAML parses `verified_on` as a date. `config.prices()` now returns it as a string; added `tests/test_config.py`. No API calls were repeated and no result logic changed.
- 2026-10-30: Smoke test passed on 5 Dev items for both models: valid single letters, logprobs present, 1 output token, `finish_reason=stop`. `max_output_tokens` stays 3.
- 2026-10-30: gpt-4.1-mini -> gpt-4.1 on Dev n=100: NO-GO (gap 1 point; minimum 5).
- 2026-10-30: Bug fix (owner request): `mizan_beats_random` passed at 0 escalations because of float rounding (0.79 vs 0.7899999999999998). It now requires `escalation_rate > 0` and `mizan accuracy > random accuracy + 1e-9`. Added `test_zero_escalation_does_not_beat_random`, confirmed failing before the fix; 28 tests pass.
- 2026-10-30: Order note: the gpt-4o-mini run started before the owner asked for the fix to come first. The fix changes analysis only, not API calls. The analysis was re-run after the fix, and the report comes from the fixed code.
- 2026-10-30: gpt-4o-mini -> gpt-4.1 on Dev n=100: GO by the coded checks (accuracy 78.0% vs 80.0% Always-Large, saving 65.4%, escalation 28%, margin AUROC 0.7747). Caveat for the owner: on the same items, Always-Small with gpt-4.1-mini has higher accuracy (79.0%) and higher saving (80.0%) than this operating point. The GO checks do not compare against other pairs' baselines. Held-out was not touched.
- 2026-10-30: Latency investigation (offline, from cached `latency_s`, file times and `client.py`): retries/backoff are not the cause. `latency_s` is timed per attempt, so it excludes backoff sleeps. In the gpt-4o-mini run, no gap between saved responses exceeded 0.03 s beyond the call's own latency, so no retry occurred. The gpt-4.1-mini and gpt-4.1 runs each show one large gap, consistent with the pause between the smoke test and the full run (position not checked). About 75-82% of calls take under 2 s and 8-13% take 20 s or more, across all three models, with no correlation to prompt size. Values cluster near 1, 2, 4, 8, 16 and 22 s, which points to connection or network stalls, but the exact cause is unproven. The client opens a new connection per request. p95 latency in the reports should not be read as model speed. Budget and retry logic unchanged.
- 2026-10-30: Total recorded experiment spend: $0.0444 of $8.00 (the ledger excludes the small probe calls).
- 2026-10-30: Coordinator approved the Dev 300 confirmation experiment. LiteLLM stays out. Held-out stays forbidden. Worst-case estimate before the runs: gpt-4o-mini $0.0179, gpt-4.1 $0.2385, gpt-4.1-mini $0.0477 (total $0.3041).
- 2026-10-30: New offline code: `src/mizan/cascade.py`, `src/mizan/dev300.py`, `scripts/analyze_cascade.py`, with `tests/test_cascade.py` and `tests/test_dev300.py`. The existing pair analysis is unchanged.
- 2026-10-30: Choices written down before the confirmation 200 were analyzed:
  - Signals: each routing stage uses `pick_signal` on the first 100 for that model. Signals are never changed based on the 200.
  - Thresholds: rate r escalates about r of the first-100 scores (`score < threshold`). Ties can make the achieved rate differ from the target; both are recorded.
  - Cascade grid: the stage-2 rate is conditional. Its threshold comes from gpt-4.1-mini's first-100 scores among items that reached stage 2 at that grid point. If none reach it (r1 = 0), the whole first-100 distribution is used.
  - Tuning ties: primary picks highest accuracy, then lowest cost, then earliest grid point.
  - A routed design that never escalates on the 200 is its first model, so it does not count as a passing design. gpt-4.1-mini -> gpt-4.1 can only meet the primary cost limit this way.
  - Design passes = not a single model, not dominated by a single model on the 200, cost at or below Always gpt-4.1-mini on the 200, and at least one escalation.
  - Cascade accepted only if it passes, has higher accuracy than the best pair on the 200, and the paired accuracy CI excludes zero. The "gain justifies complexity" condition is applied through these tests. Otherwise the best passing pair is chosen.
  - Best pair: highest accuracy on the 200 among passing pairs, then lowest cost. With none passing, the same ranking among pairs that escalate, for comparison only.
  - Decision: GO if any routed design is chosen, else NO-GO. (Superseded below: beating matched Random is now binding.)
  - Calibration: overconfidence = mean p(chosen answer) minus accuracy, compared between the 100 and the 200, alongside the AUROC drop.
  - Latency: raw `latency_s` values are stored in results.json and are not summarized in the Dev 300 report.
- 2026-10-30: Correction from the owner, applied before the confirmation analysis ran: beating conditionally matched Random is BINDING. A routed design passes only if its accuracy on the 200 is higher than the matched Random mean; otherwise it fails. The paired difference and its 95% CI are reported (each iteration uses one random routing and one item resample for both methods). The CI is reported, and a CI that includes zero is a warning, not a failure. A statistical tie with Always gpt-4.1 stays a warning only; the same warning is also shown for Always gpt-4.1-mini.
- 2026-10-30: Dev 300 confirmation ran. Coded decision: GO to held-out with gpt-4o-mini -> gpt-4.1-mini; cascade not accepted. All numbers are in `artifacts/dev300_report.md` and `artifacts/results.json`. Held-out was not used.
- 2026-10-30: Open issues for the coordinator, not changed by the executor:
  - The confirmed point (threshold 7.0, about 30% escalation) and the frozen point differ. Re-tuning on all 300, as instructed, moved to the last grid value (60% escalation, threshold 16.5). That point was never tested on separate data, and in-sample it saves only about 3.9% against Always gpt-4.1-mini, with slightly lower accuracy.
  - The gain over matched Random is small and its CI includes zero. The binding test required only a higher accuracy than the Random mean.
  - The Pareto list includes never-escalating pairs that are identical to single models; they are counted as failures in the binding test.
- 2026-10-30: Local commit and tag `dev-frozen` made as instructed. No remote, no push.
- 2026-10-30: Coordinator decision: all of Dev 300 is EXPLORATORY. The earlier confirmation report, its GO decision and the frozen `gpt-4o-mini -> gpt-4.1-mini` point (threshold 16.5) are superseded. Tag `dev-frozen` still points at that superseded freeze. Decision 13 and the earlier signal and threshold choices are replaced by the preregistration below.
- 2026-10-30: Offline Dev table: `scripts/analyze_curve.py`, `src/mizan/curve.py`, `artifacts/dev300_curve.md`. The rule selected target 30%. Accuracy 75.00% (225/300) clears the floor of 74.67% (224/300) by one item; 25% has 223/300.
- 2026-10-30: New code, no API calls: `src/mizan/perturbation.py`, `scripts/build_perturbation.py`, a `perturbation` split in `scripts/run_eval.py`. The shuffled run uses its own cache, `data/cache_option_order/`, because it keeps the same IDs and would otherwise reuse the original answers. Both scripts refuse to read held-out without `--i-have-go`. Added `tests/test_curve.py` and `tests/test_perturbation.py`.

## Preregistration (frozen before any held-out call)

Written on 2026-10-30. Held-out has not been read, called or analyzed. If a script differs from this text, this text wins and the difference is reported.

### 1. Status of Dev 300

Dev 300 is exploratory. The final hypothesis was formulated after Dev and before Held-out. The pair, the signal and the 4-point rule were all chosen after Dev results for these models had been seen, so Dev numbers are not evidence for the claims below. Held-out is used ONCE, as the only confirmation. Nothing changes after seeing it.

### 2. Architecture

`gpt-4o-mini -> gpt-4.1`. gpt-4o-mini answers unless its output is invalid or its margin is below the threshold; then gpt-4.1 answers. An escalated item costs both calls. Model names are the aliases sent to the API. On Dev they resolved to `gpt-4o-mini-2024-07-18`, `gpt-4.1-mini-2025-04-14` and `gpt-4.1-2025-04-14`. If a different snapshot is returned on Held-out it is reported, and nothing else changes.

### 3. Prompt (verbatim)

System message, identical for all models:

```text
You answer Arabic multiple-choice questions. Return exactly one uppercase ASCII letter from the available choices. Return no explanation.
```

User message, one part per line, the context line only if the item has one:

```text
{context}
{question}
A. {option 1}
B. {option 2}
...
Available choices: A, B, ...
```

Call parameters: temperature 0, logprobs true, top_logprobs 20, max_tokens 3, no structured outputs, no few-shot. Validity and parsing: `src/mizan/parsing.py` unchanged. Valid means the whole stripped output is exactly one allowed letter.

### 4. Signal

Margin = logprob(chosen letter) - logprob(best other valid letter) at the answer token. Missing competitor (`not_available`) scores +inf, so it never escalates by margin. Invalid output always escalates.

### 5. Threshold and the rule that chose it

Rule, applied exactly: "The LOWEST escalation rate whose Dev 300 accuracy is >= Always gpt-4.1 accuracy minus 4 percentage points." Grid: 0%, 5%, ..., 100% (21 points).

- Target rate: 30%. Threshold: `6.249999994711611`. Escalate when `margin < 6.249999994711611`.
- Dev 300 at this point, in sample: 90 of 300 escalated, accuracy 75.00%, cost $0.03963, saving 61.32% vs Always gpt-4.1, Mizan minus Random +4.02 points.
- The threshold is never recalibrated on Held-out, and the 30% target is not enforced there. The achieved rate is whatever the threshold produces.
- Known limit: margins cluster near 0.25 steps with floating-point noise. Six Dev items sit within 1e-4 of the threshold; 2 escalate and 4 do not. The exact value above is used anyway, with no rounding.

### 6. Prices

USD per 1M tokens, Standard tier, read from https://developers.openai.com/api/docs/pricing and verified on 2026-10-30: gpt-4o-mini 0.15 input / 0.60 output; gpt-4.1-mini 0.40 / 1.60; gpt-4.1 2.00 / 8.00. Cost = input/1M x input price + output/1M x output price. Prices are not updated after this date for this analysis.

### 7. Held-out size

500 items, all of `data/processed/heldout.jsonl`, with no exclusions. Each model is called once per item with caching. An interrupted run is resumed from the cache, and no analysis runs until all items are cached.

### 8. Bootstrap method

All intervals are two-sided 95% percentile intervals with 1000 iterations and seed 42, resampling question IDs with replacement.

- Mizan vs Random: `cascade.random_chain` with `base_seed=42`. Iteration i uses `numpy.random.default_rng(42 + i)`. It draws one random routing (invalid outputs always escalate; other escalations are drawn without replacement up to Mizan's achieved count), then one resample of question IDs applied to both methods. The point estimate is Mizan accuracy minus the mean accuracy over the 1000 seeds.
- Mizan vs a single model: `cascade.paired_bootstrap` with `seed=42`. It reports the paired accuracy difference and total cost difference on the same resampled IDs.

### 9. Preregistered claims

PRIMARY. Mizan vs matched Random at the same achieved escalation rate, as defined in section 8.
- Strong success: difference positive AND the CI excludes zero.
- Inconclusive trend, NOT a success: difference positive and the CI includes zero.
- Failure: difference zero or negative.

SECOND. Non-dominance vs Always gpt-4o-mini, Always gpt-4.1-mini and Always gpt-4.1, using the measured accuracy and total cost, with paired accuracy and cost CIs. Pareto superiority inside uncertainty is not claimed. The point is said to lie on the observed frontier only if the measured points show it.

MECHANISM (reported only). At the same acceptance rate: accepted-set accuracy vs random acceptance, gpt-4o-mini error rate inside the escalated set, and margin AUROC for gpt-4o-mini correctness.

EDUCATION LEVEL SLICES (descriptive only). For each value of `level`: N, accuracy, escalation rate, cost, and an accuracy CI where possible. Slices with N below 30 carry a small-slice warning. No claim is made from a slice.

HELD-OUT CURVE (descriptive only). The full curve may be shown with the preregistered point visually marked. No new point is ever picked from it.

### 10. Failure and anti-contamination

If the primary claim fails: threshold, signal, pair and definitions do not change. The result is reported honestly, then work STOPS before any UI work.

After the original held-out run, the prompt, threshold, margin, parsing, models and prices do not change, and no samples or slices are selected based on its result. No result after opening Held-out leads to re-tuning.

### 11. Option-order perturbation test

The name is "Option-order perturbation test". It is not a new held-out set, unseen questions, or out-of-domain data. It runs after the original held-out, with NO changes to the setup.

Construction (`src/mizan/perturbation.py`), for each held-out item:
- Seed `20261030`. Algorithm: `random.Random(f"{seed}:{id}").shuffle` (Fisher-Yates), redrawn until the displayed text order differs from the original. If that is impossible, the item is recorded in `stayed_identical`.
- Question, context and every option text are unchanged. The prompt code relabels letters A-E by position.
- Answer-key update: the new letter is the position of the original correct option in the new order.
- Asserted automatically for every item: correct answer TEXT unchanged, number of options unchanged, option texts unchanged, question and context unchanged.
- The set is built only after the original run, so the count of unchanged items is unknown until then and will be reported. On Dev 300, as a code check only, 0 of 300 stayed identical.

Models run: Always gpt-4o-mini, Always gpt-4.1-mini, Always gpt-4.1. Frozen Mizan and matched Random are computed offline from those responses, with the same threshold and no recalibration. The matched Random count is the count Mizan achieves on the shuffled run.

Reported for original AND shuffled: accuracy per model, Mizan accuracy, margin AUROC, escalation rate, cost, saving vs Always gpt-4.1, Mizan minus Random, invalid output rate, N.

Paired by question ID, original vs shuffled: change in correctness, escalation decision, routing score (mean and median absolute change where both are finite, plus the count of finite/infinite changes), and cost.

Registered claims, reported whatever the result:
- AUROC_shuffled >= AUROC_original - 0.05, on point estimates.
- Mizan minus Random keeps the same sign. A zero on either side does not count as the same sign unless both are zero.

Descriptive: accuracy drop, escalation change, saving change, number of decisions changed by option order.

Added by the executor, descriptive only: items with an option that refers to other options ("all of the above" and similar) are flagged by a fixed pattern, never removed. Moving such an option can change the question's meaning (30 of 300 flagged on Dev). The flagged count is reported, with accuracy shown for flagged and unflagged items on both runs. The registered claims always use all items.

### 12. Run order after approval

1. `python scripts/run_eval.py --small gpt-4o-mini --large gpt-4.1 --split heldout --n 500 --i-have-go`, then the same with `--small gpt-4.1-mini` (gpt-4.1 is already cached by then).
2. Offline analysis of the original held-out. The analysis script is not written yet. It is committed before step 1 and implements sections 8 to 10 as written.
3. `python scripts/build_perturbation.py --i-have-go`.
4. The same two `run_eval.py` commands with `--split perturbation`.
5. Offline analysis of the perturbation test.

## After the held-out run

Added on 2026-10-30, after the preregistration and every result above. The SHA-256 recorded in `artifacts/heldout_preflight.json` is for this file at run commit `47ee70a`, before this section existed. Nothing in this section changes a result.

- **All reported results use the original split, listed in `artifacts/split_ids.json`.** No data, cache or result was regenerated.
- **What the original split is.** Dev and Held-out share 0 of 40 Subject x Level strata: held-out is disjoint by subject and level together. It is not disjoint by subject alone. 7 of its 15 subjects also appear in Dev at other levels, covering 220 of 500 items; the other 280 are in subjects absent from Dev. Results describe those 25 strata, equally weighted, not ArabicMMLU as a whole.
- **Wording.** The coordinator's text called this split "subject-disjoint". Because 220 items are in subjects that also appear in Dev, the executor wrote "subject-by-level-disjoint" in the app and README, and reported the change. The sentence is the one constant `SPLIT_SENTENCE` in `src/mizan/story.py`.
- **Split bug fixed, code only.** `stratified_split` dealt items across 40 strata and then assigned them with a pattern repeating every 8, so each stratum landed in one split. It now divides each stratum on its own; on the real data the fixed code shares 40 of 40 strata. Regression tests are in `tests/test_data_and_metrics.py`.
- **`scripts/prepare_data.py` now rebuilds the original split from its IDs by default**, because the fix would otherwise silently produce different items. Checked in memory against the cached dataset: Dev and Held-out are identical to the files used for the runs. `--new-split` builds a new split, which is a new experiment.
- **`scripts/analyze_heldout.py` is bound to the run.** It refuses to run once HEAD differs from the run commit. Offline recomputation uses `scripts/recompute_offline.py`, which runs the same analysis functions on `artifacts/heldout_per_item.json` (IDs and outcomes, no question text) and writes nothing.
- **Demo examples use a fixed rule**, in `SELECTION_RULE` in `src/mizan/demo.py`. An item with no competing option has no measured margin, so it is not eligible as the highest margin. Translations are by Claude (AI), not reviewed by a professional translator.
- **The replay uses the first 100 held-out items in run order**, a fixed rule. The app states that this sample differs from the full result.
- **Live demo calls** use the frozen prompt, model settings, parsing and threshold, with a shorter timeout and fewer retries so a demo fails fast. Their spend goes to `artifacts/demo_ledger.jsonl` (git-ignored), capped at the $2 reserve, not to the experiment ledger.
- **Dataset license.** The ArabicMMLU GitHub README states CC BY-NC-SA 4.0 and the Hugging Face card states CC BY-NC 4.0. Both allow non-commercial redistribution with attribution, so `artifacts/demo_examples.json` and `artifacts/demo_translations.json` are tracked under the stricter license. No other question text is tracked.
- **Demo rule change, a presentation choice only.** On the coordinator's decision, the high-confidence demo example now excludes religious subjects (`RELIGIOUS_SUBJECTS` in `src/mizan/demo.py`, which is Islamic Studies among the held-out subjects). The chosen item moved from ID 235 to ID 6398. The lower-confidence rule is unchanged. This has no effect on routing, on the evaluation items or on any result: `artifacts/heldout_results.json` and `artifacts/heldout_per_item.json` are unchanged.
- **Non-commercial entry and code license.** The coordinator confirmed the hackathon entry is non-commercial, so the demo questions and translations stay tracked under CC BY-NC-SA 4.0 with attribution. The code is under the MIT License (`LICENSE`), which does not cover dataset content.
- **Product page redesign, presentation only.** On the coordinator's request the app was rebuilt as a custom page inside Streamlit. No result, threshold, prompt or evaluation call changed. Four consequences are worth recording:
  - **The replay now covers all 500 held-out requests.** This supersedes the first-100 rule above, so the replay ends on the same numbers as the headline results.
  - **The two demo examples always show the recorded run.** Switching between them no longer makes a live call. Only "Route with MIZAN" can spend money.
  - **The 40% figure has no confidence interval.** `heldout_results.json` records none for the relative error reduction, and computing one would be a new number, so the page says so and shows the related accuracy gain over matched random with its interval.
  - **The chart library is vendored.** `app/assets/vendor/plotly-basic-2.35.2.min.js` (MIT) is inlined into the page so the chart works without a CDN. `app/assets/cover-reference.png` is a design reference and is not shown on the page.
- **The live form moved into the Demo section, on the owner's request.** With `MIZAN_LIVE_LAB=1` it replaces the form that sat after the footer. It stays a native Streamlit form, so every model call stays in Python, and `app/web/page.js` pins it over a slot reserved in the Demo section, which keeps the page in one iframe. It uses the same `live_request`, prompt, parser, margin, threshold, prices and demo ledger. A failed gpt-4.1 call now shows no final answer, and never falls back to the first answer. Live runs are labelled "LIVE API RUN", are not saved beyond the token and cost counts in the local ledger, and are not part of any recorded result.
- **The Live Lab is its own section, which supersedes pinning the form over the Demo section.** Pinning caused jumps, repeated content and gaps in the browser. The form now sits after the page iframe in an `st.fragment`, so loading an example or running it reruns only that section. The Demo button only scrolls to it. The live routing logic did not change.
- **The Live Lab takes free typing and loads samples from a dropdown, on the owner's request.** A Clear button and a "Load a sample" dropdown replace the two example buttons, and the recorded items left the Live Lab. The three samples were written for it and are not from ArabicMMLU or the recorded examples. The form sets `enter_to_submit=False`, because Enter otherwise pressed its first submit button, which could make a paid call. The grammar sample is listed second because it escalated when run live (margin 2.75; the poetry sample was accepted at 15.625). In that run gpt-4.1 answered B against the known correct A, so the page showed "Incorrect". These two runs are product checks, not evaluation results. The routing logic did not change.
- **The Live Lab sits directly under the recorded examples, which supersedes placing it after the page.** With `MIZAN_LIVE_LAB=1` the page is two iframes, Hero to Demo and Results to the footer, with the Live Lab between them, and a "Live Demo" header link replaces the Demo section's scroll button. With the lab off the page stays one iframe. The grammar sample now loads with no known correct option, so a live run shows no verdict, and the poetry sample is no longer labelled hard. The routing logic did not change.
