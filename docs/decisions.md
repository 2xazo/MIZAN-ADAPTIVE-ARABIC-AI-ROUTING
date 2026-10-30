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
