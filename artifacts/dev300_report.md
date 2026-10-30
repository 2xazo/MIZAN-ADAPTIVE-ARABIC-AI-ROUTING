# MIZAN Dev 300 confirmation report

Generated: 2026-10-30T17:13:08+0300  
Items: first 100 (exploration), next 200 (confirmation). Held-out was not used.

**Decision: GO to held-out.** gpt-4o-mini -> gpt-4.1-mini passes non-dominance, the cost limit and beats matched Random on the confirmation 200.

**Warnings:**
- Accuracy vs Always gpt-4.1-mini is statistically tied on the 200 (CI includes zero).
- The gain over matched Random has a 95% CI that includes zero.

Thresholds and the operating point were chosen on the first 100 and applied unchanged to the 200. Primary objective: highest accuracy with cost at or below Always gpt-4.1-mini.

## 1. First-100 results (exploration, optimistic)

| Design | Accuracy | Cost | Target escalation | Achieved escalation | Random accuracy (mean) | Oracle accuracy |
|---|---|---|---|---|---|---|
| gpt-4o-mini | 73.0% | $0.00261 | none | none | - | - |
| gpt-4.1-mini | 79.0% | $0.00696 | none | none | - | - |
| gpt-4.1 | 80.0% | $0.03481 | none | none | - | - |
| gpt-4o-mini -> gpt-4.1-mini | 78.0% | $0.00519 | 30.0% | 30.0% | 74.7% | 88.0% |
| gpt-4o-mini -> gpt-4.1 | 73.0% | $0.00261 | 0.0% | 0.0% | 73.0% | 83.0% |
| gpt-4.1-mini -> gpt-4.1 | 79.0% | $0.00696 | 0.0% | 0.0% | 79.0% | 89.0% |
| gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1 | 80.0% | $0.00594 | 30.0% / 10.0% | 30.0% / 10.0% | 74.7% | 91.0% |

## 2. Confirmation-200 results (binding)

| Design | Accuracy | Cost | Target escalation | Achieved escalation | Random accuracy (mean) | Oracle accuracy |
|---|---|---|---|---|---|---|
| gpt-4o-mini | 65.0% | $0.00507 | none | none | - | - |
| gpt-4.1-mini | 70.5% | $0.01353 | none | none | - | - |
| gpt-4.1 | 78.0% | $0.06763 | none | none | - | - |
| gpt-4o-mini -> gpt-4.1-mini | 68.0% | $0.01001 | 30.0% | 36.5% | 67.0% | 79.0% |
| gpt-4o-mini -> gpt-4.1 | 65.0% | $0.00507 | 0.0% | 0.0% | 65.0% | 81.0% |
| gpt-4.1-mini -> gpt-4.1 | 70.5% | $0.01353 | 0.0% | 0.0% | 70.5% | 83.5% |
| gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1 | 68.5% | $0.01099 | 30.0% / 10.0% | 36.5% / 5.5% | 67.1% | 84.5% |

## 3. Combined 300 results (exploratory, not confirmatory)

| Design | Accuracy | Cost | Target escalation | Achieved escalation | Random accuracy (mean) | Oracle accuracy |
|---|---|---|---|---|---|---|
| gpt-4o-mini | 67.7% | $0.00768 | none | none | - | - |
| gpt-4.1-mini | 73.3% | $0.02049 | none | none | - | - |
| gpt-4.1 | 78.7% | $0.10244 | none | none | - | - |
| gpt-4o-mini -> gpt-4.1-mini | 71.3% | $0.01520 | 30.0% | 34.3% | 69.6% | 82.0% |
| gpt-4o-mini -> gpt-4.1 | 67.7% | $0.00768 | 0.0% | 0.0% | 67.7% | 81.7% |
| gpt-4.1-mini -> gpt-4.1 | 73.3% | $0.02049 | 0.0% | 0.0% | 73.3% | 85.3% |
| gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1 | 72.3% | $0.01692 | 30.0% / 10.0% | 34.3% / 6.8% | 69.7% | 86.7% |

## 4. Accuracy and cost: every single model, pair and the cascade

| Design | Kind | Acc 100 | Cost 100 | Acc 200 | Cost 200 | Acc 300 | Cost 300 |
|---|---|---|---|---|---|---|---|
| gpt-4o-mini | single | 73.0% | $0.00261 | 65.0% | $0.00507 | 67.7% | $0.00768 |
| gpt-4.1-mini | single | 79.0% | $0.00696 | 70.5% | $0.01353 | 73.3% | $0.02049 |
| gpt-4.1 | single | 80.0% | $0.03481 | 78.0% | $0.06763 | 78.7% | $0.10244 |
| gpt-4o-mini -> gpt-4.1-mini | pair | 78.0% | $0.00519 | 68.0% | $0.01001 | 71.3% | $0.01520 |
| gpt-4o-mini -> gpt-4.1 | pair | 73.0% | $0.00261 | 65.0% | $0.00507 | 67.7% | $0.00768 |
| gpt-4.1-mini -> gpt-4.1 | pair | 79.0% | $0.00696 | 70.5% | $0.01353 | 73.3% | $0.02049 |
| gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1 | cascade | 80.0% | $0.00594 | 68.5% | $0.01099 | 72.3% | $0.01692 |

Secondary objective (report only): lowest cost with accuracy at or above Always gpt-4.1 minus 2 points, tuned on the first 100.

| Design | Target escalation | Acc 100 | Cost 100 | Acc 200 | Cost 200 |
|---|---|---|---|---|---|
| gpt-4o-mini -> gpt-4.1-mini | 30.0% | 78.0% | $0.00519 | 68.0% | $0.01001 |
| gpt-4o-mini -> gpt-4.1 | 30.0% | 78.0% | $0.01550 | 74.5% | $0.02976 |
| gpt-4.1-mini -> gpt-4.1 | 0.0% | 79.0% | $0.00696 | 70.5% | $0.01353 |
| gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1 | 30.0% / 0.0% | 78.0% | $0.00519 | 68.0% | $0.01001 |

## 5. Pareto frontier and non-dominance (confirmation 200)

Frontier: `gpt-4o-mini`, `gpt-4.1-mini`, `gpt-4.1`, `gpt-4o-mini -> gpt-4.1-mini`, `gpt-4o-mini -> gpt-4.1`, `gpt-4.1-mini -> gpt-4.1`, `gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1`

| Design | Dominated by a single model | Cost within limit | Never escalates | Beats matched Random | Passes |
|---|---|---|---|---|---|
| gpt-4o-mini | no | True | - | - | baseline |
| gpt-4.1-mini | no | True | - | - | baseline |
| gpt-4.1 | no | False | - | - | baseline |
| gpt-4o-mini -> gpt-4.1-mini | no | True | False | True | True |
| gpt-4o-mini -> gpt-4.1 | no | True | True | False | False |
| gpt-4.1-mini -> gpt-4.1 | no | True | True | False | False |
| gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1 | no | True | False | True | True |

## 6. AUROC per stage

| Stage | Model | Signal | AUROC 100 | AUROC 200 | Drop | Overconfidence 100 | Overconfidence 200 |
|---|---|---|---|---|---|---|---|
| 1 | gpt-4o-mini | margin | 0.7747 | 0.7925 | -0.0178 | 22.7% | 30.0% |
| 2 | gpt-4.1-mini | margin | 0.7932 | 0.7878 | 0.0054 | 15.9% | 21.8% |

Overconfidence is mean p(chosen answer) minus accuracy. Signals were not changed after seeing the 200. All signals, for information:

| Model | Set | raw_logprob | normalized | margin |
|---|---|---|---|---|
| gpt-4o-mini | first_100 | 0.7448 | 0.7189 | 0.7747 |
| gpt-4o-mini | confirmation_200 | 0.7605 | 0.7184 | 0.7925 |
| gpt-4.1-mini | first_100 | 0.7857 | 0.5802 | 0.7932 |
| gpt-4.1-mini | confirmation_200 | 0.7862 | 0.5786 | 0.7878 |

## 7. Target vs achieved thresholds and escalation rates

Stage-2 rates are conditional: a share of the items that reached stage 2.

| Design | Thresholds | Target | Achieved 100 | Achieved 200 | Achieved 300 |
|---|---|---|---|---|---|
| gpt-4o-mini -> gpt-4.1-mini | 7.0000 | 30.0% | 30.0% | 36.5% | 34.3% |
| gpt-4o-mini -> gpt-4.1 | -inf | 0.0% | 0.0% | 0.0% | 0.0% |
| gpt-4.1-mini -> gpt-4.1 | -inf | 0.0% | 0.0% | 0.0% | 0.0% |
| gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1 | 7.0000 / 0.2500 | 30.0% / 10.0% | 30.0% / 10.0% | 36.5% / 5.5% | 34.3% / 6.8% |

## 8. Stop distribution (share stopped at each model)

| Design | Set | Stopped at |
|---|---|---|
| gpt-4o-mini -> gpt-4.1-mini | first_100 | gpt-4o-mini: 70.0%, gpt-4.1-mini: 30.0% |
| gpt-4o-mini -> gpt-4.1-mini | confirmation_200 | gpt-4o-mini: 63.5%, gpt-4.1-mini: 36.5% |
| gpt-4o-mini -> gpt-4.1 | first_100 | gpt-4o-mini: 100.0%, gpt-4.1: 0.0% |
| gpt-4o-mini -> gpt-4.1 | confirmation_200 | gpt-4o-mini: 100.0%, gpt-4.1: 0.0% |
| gpt-4.1-mini -> gpt-4.1 | first_100 | gpt-4.1-mini: 100.0%, gpt-4.1: 0.0% |
| gpt-4.1-mini -> gpt-4.1 | confirmation_200 | gpt-4.1-mini: 100.0%, gpt-4.1: 0.0% |
| gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1 | first_100 | gpt-4o-mini: 70.0%, gpt-4.1-mini: 27.0%, gpt-4.1: 3.0% |
| gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1 | confirmation_200 | gpt-4o-mini: 63.5%, gpt-4.1-mini: 34.5%, gpt-4.1: 2.0% |

## 9. Conditionally matched Random (1000 seeds)

Binding on the 200: a design must have higher accuracy than the Random mean. The paired difference resamples the same items for both methods.

| Design | Set | Mizan accuracy | Random mean | Random 95% interval | Paired difference (points) | Paired 95% CI (points) | Mizan cost | Random cost (mean) |
|---|---|---|---|---|---|---|---|---|
| gpt-4o-mini -> gpt-4.1-mini | first_100 | 78.0% | 74.7% | [70.0%, 79.0%] | +3.3 | [-5.0, +12.0] | $0.00519 | $0.00471 |
| gpt-4o-mini -> gpt-4.1-mini | confirmation_200 | 68.0% | 67.0% | [64.0%, 70.5%] | +1.0 | [-5.0, +6.5] | $0.01001 | $0.00995 |
| gpt-4o-mini -> gpt-4.1 | first_100 | 73.0% | 73.0% | [73.0%, 73.0%] | -0.0 | [+0.0, +0.0] | $0.00261 | $0.00261 |
| gpt-4o-mini -> gpt-4.1 | confirmation_200 | 65.0% | 65.0% | [65.0%, 65.0%] | -0.0 | [+0.0, +0.0] | $0.00507 | $0.00507 |
| gpt-4.1-mini -> gpt-4.1 | first_100 | 79.0% | 79.0% | [79.0%, 79.0%] | +0.0 | [+0.0, +0.0] | $0.00696 | $0.00696 |
| gpt-4.1-mini -> gpt-4.1 | confirmation_200 | 70.5% | 70.5% | [70.5%, 70.5%] | +0.0 | [+0.0, +0.0] | $0.01353 | $0.01353 |
| gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1 | first_100 | 80.0% | 74.7% | [70.0%, 79.0%] | +5.3 | [-4.0, +14.0] | $0.00594 | $0.00579 |
| gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1 | confirmation_200 | 68.5% | 67.1% | [64.0%, 70.5%] | +1.4 | [-4.5, +7.0] | $0.01099 | $0.01130 |

## 10. Oracle (uses ground truth: theoretical upper bound only)

| Design | Set | Accuracy | Cost | Stopped at each model |
|---|---|---|---|---|
| gpt-4o-mini -> gpt-4.1-mini | first_100 | 88.0% | $0.00380 | 85.0% / 15.0% |
| gpt-4o-mini -> gpt-4.1-mini | confirmation_200 | 79.0% | $0.00698 | 86.0% / 14.0% |
| gpt-4o-mini -> gpt-4.1 | first_100 | 83.0% | $0.00489 | 90.0% / 10.0% |
| gpt-4o-mini -> gpt-4.1 | confirmation_200 | 81.0% | $0.01604 | 84.0% / 16.0% |
| gpt-4.1-mini -> gpt-4.1 | first_100 | 89.0% | $0.01114 | 90.0% / 10.0% |
| gpt-4.1-mini -> gpt-4.1 | confirmation_200 | 83.5% | $0.02231 | 87.0% / 13.0% |
| gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1 | first_100 | 91.0% | $0.00482 | 82.0% / 15.0% / 3.0% |
| gpt-4o-mini -> gpt-4.1-mini -> gpt-4.1 | confirmation_200 | 84.5% | $0.01332 | 80.5% / 14.0% / 5.5% |

## 11. Paired bootstrap (1000 iterations, confirmation 200)

Cascade minus best pair (`gpt-4o-mini -> gpt-4.1-mini`):
- Accuracy difference: +0.5 points, 95% CI [+0.0, +1.5], excludes zero: False
- Cost difference: +0.00098 USD, 95% CI [+0.00021, +0.00205], excludes zero: True

Chosen design minus Always gpt-4o-mini:
- Accuracy difference: +3.0 points, 95% CI [-2.0, +8.0], excludes zero: False
- Cost difference: +0.00494 USD, 95% CI [+0.00333, +0.00700], excludes zero: True

Chosen design minus Always gpt-4.1-mini:
- Accuracy difference: -2.5 points, 95% CI [-6.5, +1.0], excludes zero: False
- Cost difference: -0.00352 USD, 95% CI [-0.00539, -0.00181], excludes zero: True

Chosen design minus Always gpt-4.1:
- Accuracy difference: -10.0 points, 95% CI [-15.5, -5.0], excludes zero: True
- Cost difference: -0.05762 USD, 95% CI [-0.07109, -0.04628], excludes zero: True

## 12. Actual cumulative cost

$0.1306 of $8.00 (recorded in the cost ledger).

## 13. Best simple non-dominated design

`gpt-4o-mini -> gpt-4.1-mini`: accuracy 68.0%, cost $0.01001 on the 200.

## 14. Does the cascade add a meaningful improvement?

No. Beats best pair on the 200: True. Accuracy CI excludes zero: False. Passes binding test: True.

## 15. Decision

**GO to held-out.** gpt-4o-mini -> gpt-4.1-mini passes non-dominance, the cost limit and beats matched Random on the confirmation 200.

Frozen before held-out: `gpt-4o-mini -> gpt-4.1-mini`, signals {'gpt-4o-mini': 'margin'}, thresholds ['16.5000'], retuned on all 300 (in-sample, exploratory). In-sample accuracy 73.0%, cost $0.01970. These in-sample numbers are not a performance claim.

