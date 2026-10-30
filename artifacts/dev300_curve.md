# MIZAN Dev 300 escalation table (exploratory)

Pair: `gpt-4o-mini -> gpt-4.1`. Signal: margin. Items: all 300 Dev. Random: 1000 seeds, same number of escalated items. Held-out was not used. Dev 300 is exploratory; none of these numbers is a performance claim. The final hypothesis is formulated after Dev and before Held-out. Held-out is used once, as the only confirmation, and nothing changes after seeing it.

| Always | Accuracy | Cost |
|---|---|---|
| gpt-4o-mini | 67.67% | $0.00768 |
| gpt-4.1-mini | 73.33% | $0.02049 |
| gpt-4.1 | 78.67% | $0.10244 |

| Target | Threshold | Escalated | Achieved | Accuracy | Cost | Saving vs top | Acc diff vs top (pts) | Random mean | Mizan - Random (pts) | Accepted-set acc | Small error in escalated | Dominated by |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0% | -inf | 0 | 0.00% | 67.67% | $0.00768 | 92.50% | -11.00 | 67.67% | +0.00 | 67.67% | n/a | none |
| 5% | 0.7500 | 15 | 5.00% | 69.00% | $0.01345 | 86.87% | -9.67 | 68.21% | +0.79 | 69.47% | 66.67% | none |
| 10% | 1.7500 | 30 | 10.00% | 70.67% | $0.01726 | 83.15% | -8.00 | 68.75% | +1.92 | 71.48% | 66.67% | none |
| 15% | 2.7500 | 45 | 15.00% | 72.33% | $0.02602 | 74.60% | -6.33 | 69.34% | +3.00 | 74.12% | 68.89% | gpt-4.1-mini |
| 20% | 4.0000 | 60 | 20.00% | 73.67% | $0.03323 | 67.56% | -5.00 | 69.83% | +3.83 | 75.83% | 65.00% | none |
| 25% | 5.2500 | 75 | 25.00% | 74.33% | $0.03658 | 64.29% | -4.33 | 70.45% | +3.88 | 76.89% | 60.00% | none |
| 30% | 6.2500 | 90 | 30.00% | 75.00% | $0.03963 | 61.32% | -3.67 | 70.98% | +4.02 | 79.52% | 60.00% | none |
| 35% | 7.2500 | 105 | 35.00% | 75.67% | $0.04587 | 55.22% | -3.00 | 71.57% | +4.09 | 81.54% | 58.10% | none |
| 40% | 9.0000 | 120 | 40.00% | 76.33% | $0.04988 | 51.31% | -2.33 | 72.12% | +4.22 | 82.22% | 54.17% | none |
| 45% | 10.7500 | 135 | 45.00% | 76.67% | $0.05396 | 47.33% | -2.00 | 72.59% | +4.08 | 83.64% | 51.85% | none |
| 50% | 13.5000 | 150 | 50.00% | 77.33% | $0.06189 | 39.58% | -1.33 | 73.11% | +4.23 | 86.67% | 51.33% | none |
| 55% | 15.0000 | 165 | 55.00% | 77.33% | $0.06476 | 36.79% | -1.33 | 73.76% | +3.57 | 87.41% | 48.48% | none |
| 60% | 16.5000 | 180 | 60.00% | 78.00% | $0.06775 | 33.87% | -0.67 | 74.24% | +3.76 | 90.00% | 47.22% | none |
| 65% | 18.5000 | 195 | 65.00% | 78.33% | $0.07454 | 27.24% | -0.33 | 74.81% | +3.52 | 92.38% | 45.64% | none |
| 70% | 20.2500 | 210 | 70.00% | 78.67% | $0.07928 | 22.61% | +0.00 | 75.40% | +3.26 | 95.56% | 44.29% | none |
| 75% | 21.1250 | 225 | 75.00% | 78.67% | $0.08233 | 19.63% | +0.00 | 75.91% | +2.76 | 96.00% | 41.78% | none |
| 80% | 23.0000 | 240 | 80.00% | 78.67% | $0.09386 | 8.38% | +0.00 | 76.47% | +2.19 | 96.67% | 39.58% | none |
| 85% | 24.0000 | 255 | 85.00% | 78.67% | $0.09923 | 3.14% | +0.00 | 77.03% | +1.63 | 97.78% | 37.65% | none |
| 90% | 25.1250 | 270 | 90.00% | 78.67% | $0.10472 | -2.22% | +0.00 | 77.55% | +1.11 | 100.00% | 35.93% | gpt-4.1 |
| 95% | 27.1250 | 285 | 95.00% | 78.67% | $0.10750 | -4.94% | +0.00 | 78.12% | +0.55 | 100.00% | 34.04% | gpt-4.1 |
| 100% | escalate all | 300 | 100.00% | 78.67% | $0.11013 | -7.50% | +0.00 | 78.67% | -0.00 | n/a | 32.33% | gpt-4.1 |

Top = Always gpt-4.1. Invalid small outputs count as errors and always escalate. Thresholds use `score < threshold`. Margins cluster near 0.25 steps with tiny floating-point noise, so that noise can split items of nearly equal margin at a threshold.

Rule: the LOWEST escalation rate whose Dev 300 accuracy is >= Always top accuracy minus 4 percentage points.

**Operating point: target 30%, margin threshold 6.2500, 90 of 300 escalated, accuracy 75.00%.**
