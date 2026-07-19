# Sonar visibility truth test

Runtime-spawned object dead-ahead of the sonar; difference against the no-object baseline (A) is the object's acoustic signature.


## custom engine

| condition | pose | max | nonzero bins | mean|diff| vs A | bit-identical to A |
|---|---|---|---|---|---|
| A | headon | 0.47124 | 45942 | 0.0 | True |
| A | left45 | 0.4705 | 59335 | 0.0 | True |
| A | right45 | 0.47065 | 49686 | 0.0 | True |
| BOX | headon | 0.47124 | 49655 | 0.006367 | False |
| BOX | left45 | 0.4705 | 60503 | 0.004426 | False |
| BOX | right45 | 0.47065 | 52228 | 0.005334 | False |
| CYL | headon | 0.47124 | 49437 | 0.006506 | False |
| CYL | left45 | 0.4705 | 62001 | 0.004573 | False |
| CYL | right45 | 0.47065 | 52393 | 0.005751 | False |
| OUTFALL | headon | 0.47124 | 43740 | 0.004566 | False |
| OUTFALL | left45 | 0.4705 | 55764 | 0.005445 | False |
| OUTFALL | right45 | 0.47065 | 47905 | 0.004259 | False |

## Verdicts (head-on pose)

| engine:condition | spawned object visible? | changed bins | mean|diff| |
|---|---|---|---|
| custom:BOX | **YES** | 33498 | 0.006367 |
| custom:CYL | **YES** | 33652 | 0.006506 |
| custom:OUTFALL | **YES** | 30665 | 0.004566 |