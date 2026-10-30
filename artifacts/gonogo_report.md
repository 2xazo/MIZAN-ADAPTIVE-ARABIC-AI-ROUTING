# MIZAN Go/No-Go report

Generated: 2026-10-30T16:15:45+0300  
Pairs tried on Dev: 2  
Spent so far: $0.0444 of $8.00

## Selected pair: gpt-4o-mini -> gpt-4.1  (Dev n=100)

**Decision: GO**

> Threshold and signal were tuned AND measured on the same Dev items: optimistic estimate.

| Strategy | Accuracy | Saving vs Large | Escalation | Cost (USD) | p95 latency (s) |
|---|---|---|---|---|---|
| always_small | 73.0% | 92.5% | 0.0% | 0.00261 | 21.97 |
| always_large | 80.0% | 0.0% | 100.0% | 0.03481 | 22.02 |
| random | 75.0% | 64.1% | 28.0% | 0.01251 | 22.70 |
| mizan | 78.0% | 65.4% | 28.0% | 0.01204 | 22.13 |
| oracle | 83.0% | 86.0% | 10.0% | 0.00489 | 21.97 |

Gap Large-Small: 7.0 points. Invalid small outputs: 0.
Selected signal: `margin`, threshold: 6.750000002646574

| Signal | AUROC | Coverage of valid items |
|---|---|---|
| raw_logprob | 0.7448 | 100.0% |
| normalized | 0.7189 | 96.0% |
| margin | 0.7747 | 100.0% |

| GO check | Pass |
|---|---|
| small_accuracy>=min | True |
| gap_points>=min | True |
| auroc>=min | True |
| mizan_beats_random | True |
| operating_point_loss<=max_and_saving>=min | True |

Tokens: {'small_input': 17005, 'small_output': 100, 'large_input': 17005, 'large_output': 100}

## Other pairs tried
- gpt-4.1-mini -> gpt-4.1: NO-GO
