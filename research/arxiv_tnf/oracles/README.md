# Reference implementations the published figures are derived from

Every number in `docs/reports/upstream/` that compares TNF against a competing
format is produced by a rig that imports one of these. They lived in a session
scratchpad until W981, where `tri audit` reported

    FAIL  rungs     oracles not found; set T27_CONFORMANCE

on a bench where the files were present -- the discovery path contains a
per-session identifier, so the gate went dark whenever the session changed. A
gate whose inputs vanish on restart is not a gate, and figures whose oracle a
referee cannot open are not reproducible. They are committed here for both
reasons.

| file | what it defines |
|------|-----------------|
| `tnf_ref.py` | `TNFFormat(w, k)` -- the ternary format under test, and its rungs |
| `tnf_ladder_versions.py` | the ladder's historical encodings, kept apart from the current one |
| `gf_ref.py` | the GF-T / golden-ratio reference |
| `fp8_ref.py` | IEEE-style fp8 (`e4m3`, `e5m2`) with and without subnormals |
| `bf16_ref.py` | bfloat16 |
| `posit_ref.py` | posits, `es` configurable |
| `takum_ref.py` | takum |

`tri rungs`, `tri grid`, `tri sweep` and `tri cost` find them here by default;
`T27_CONFORMANCE` still overrides.
