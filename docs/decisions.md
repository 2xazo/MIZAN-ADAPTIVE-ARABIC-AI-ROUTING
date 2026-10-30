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
