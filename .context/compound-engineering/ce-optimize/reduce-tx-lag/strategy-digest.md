# Strategy digest — reduce-tx-lag (final)

## Results
- Kept: #2 beam≤2 pipeline, #3 beam≤1 pipeline
- Reverted: #1 NLLB-only clamp, #4 punct-skip (neutral on harness)
- Best tx_lag_p95_ms: 16.778 (baseline 34.776, ≈−52%)

## Learnings
1. Synthetic harness only observes decode dict + text length from pipeline.
2. Short-caption beam clamp is the winning lever here.
3. Punct-skip is plausible live but invisible on this fixture.

## Caution before product merge
Always-on beam≤1 for len<24 overrides Traducciones presets for typical captions.
Prefer gating behind `opt_prefer_fast_translation` or a dedicated opt flag.

## Stopped
max_iterations=4
