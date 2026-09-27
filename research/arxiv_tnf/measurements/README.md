# Measurement records backing the TNF paper

Every file here is a machine-written record produced by a script in this
repository, copied verbatim. Nothing in this directory was edited by hand.

| file | what it records | status |
|---|---|---|
| `tnf_downstream_bayesian_si_2026-08-13.json` | outcome of one numerical task (MAP estimate of the solar gravitational parameter in raw SI) rather than a round-trip error; backs the downstream table | current |
| `gen_downstream_bayesian_si.py` | the generator for the above; deterministic under seed 20260813 | current |
| `strict_range_2026-08-13g.json` | per-workload comparison under strict representability against range bounds; backs the qualifying-pair count | current |
| `workloads_strict_2026-08-13g.json` | the workload/rung pairs and their ratios | current |
| `per_rung_2026-08-13g.json` | per-rung threshold sweep; backs the rung-threshold table | current |
| `centering_2026-08-13f.json` | rescaling invariance test that removed the absolute-magnitude window | current |
| `inside_window_2026-08-13f.json` | rows inside the window | current |
| `gpt2_window_2026-08-13e.json` | GPT-2 block-0 intermediates, the negative result inside neural inference | current |
| `crossover_2026-08-13e.json`, `crossover2_2026-08-13e.json` | crossover computation before and after the straight-line fit was withdrawn | second file current |
| `pnr_seed_sweep_2026-08-19.json` | five placer seeds on one netlist, `tnf_cost_e2m11_add_top` on xc7a200tfbg676-1; Fmax 379.65-422.65 MHz at an identical 467 LUTs. Raw nextpnr logs in `pnr_logs/`, sha256 of each recorded in the JSON. NOT the CI part (fbg484-2) and NOT a substitute for the sweep | current |
| `blockpct_2026-08-20.json` | within-block span percentiles (block 32, SmolLM2-135M) behind `tab:blockpct`; the span definition (lower-median convention) is part of the record | current |
| `gen_blockpct.py` | the generator for the above; deterministic, checkpoint pinned by snapshot + sha256 | current |
| `weight_ranges_2026-08-20.json` | block-scale occupancy 8.32/9.12 binades (SmolLM2-135M / Qwen2.5-0.5B), the 268.95x median channel dynamic range, and the 210-tensor per-tensor scale spans behind `thm:barrelrange`'s robust reading | current |
| `gen_weight_ranges.py` | the generator for the above; deterministic, both checkpoints pinned by snapshot + sha256 | current |
| `regret_sweep_2026-08-20.json` | full rerun of the 8-bit exponent-width sweep (fp32 baseline + BNF8 E=1..5 + TNF8 Et=1..3, 40 windows) behind the paper's regret sentence and the falsified width-rule predictions | current |
| `gen_regret_sweep.py` | the generator for the above; quant/levels/eval copied verbatim from `research/block/four_families.py`, weights addressed at the HF-cache snapshot the original's symlink resolved to | current |

Two earlier records are deliberately **not** copied here: an invariance record
whose harness tested representability against zero rather than against the range
bounds, and the pre-fix workload sweep taken with the same harness. Both are
superseded by the files above; the defect and its consequences are stated in the
paper rather than hidden.

## W994: the TNF4/TNF8/TNF16 records recomputed on the trit-word grid

Up to W993 `tnf_ref.decode` read an exponent field above `offset_max` as an
ordinary power of two, although `tnf_ref.encode` never produces such a word.
Every rig that built its value grid by decoding all codes therefore trained,
counted and synthesised on values the format does not have (TNF4: 57 values up
to 3072 instead of 29 up to 12). Since W994 `decode` raises on such a code and
the rigs build their grids from TNF words only; `decode_every_code` keeps the
withdrawn reading for comparisons. The records below were rerun with the fixed
oracle (`T27_CONFORMANCE=oracles`, output in a scratch `T27_WORK`) and copied
here verbatim under a `w994` name. Where a rerun also carries TNF-free rows
(the fp6 arms of `blockscale`, `blockquant`, `macrig` and `accrig`, the fp rows of
`census963` and `rung16`), `verify_numbers.py` checks that they are identical to
the record the rerun replaces. The earlier records stay in this directory as the
history of the defect; `verify_numbers.py` no longer reads their TNF rows as
current.

| file | command (environment, then rig) |
|---|---|
| `stability_w994_mnist_gs_3ep.json` | `FORMATS=TNF4 TASK=mnist EPOCHS=3 stability.py` |
| `stability_w994_mnist_gs_10ep.json` | `FORMATS=TNF4 TASK=mnist EPOCHS=10 stability.py` |
| `stability_w994_mnist_gs_30ep.json` | `FORMATS=TNF4 TASK=mnist EPOCHS=30 stability.py` |
| `stability_w994_mnist_nogs_3ep.json` | `FORMATS=TNF4 TASK=mnist EPOCHS=3 GRAD_SCALE=0 stability.py` |
| `stability_w994_mnist_pct0.999_3ep.json` | `FORMATS=TNF4 TASK=mnist EPOCHS=3 INIT_PCT=0.999 stability.py` |
| `lsq_ablation_w994_qp3072_3ep.json` | `FORMATS=TNF4 TASK=mnist EPOCHS=3 LSQ_QP=3072 stability.py` |
| `lsq_ablation_w994_qp3072_10ep.json` | `FORMATS=TNF4 TASK=mnist EPOCHS=10 LSQ_QP=3072 stability.py` |
| `lsq_ablation_w994_nogs_10ep.json` | `FORMATS=TNF4 TASK=mnist EPOCHS=10 GRAD_SCALE=0 stability.py` |
| `lsq_ablation_w994_pct0.999_nogs_3ep.json` | `FORMATS=TNF4 TASK=mnist EPOCHS=3 INIT_PCT=0.999 GRAD_SCALE=0 stability.py` |
| `lsq_ablation_w994_everycode_qp12_10ep.json` | `FORMATS=TNF4 TASK=mnist EPOCHS=10 LSQ_QP=12 TNF_GRID=every-code stability.py` (the withdrawn grid, trained on purpose) |
| `scaleconv_w994_3ep.json` | `FORMATS=TNF4 EPOCHS=3 scaleconv.py` |
| `blockquant_w994_3ep.json` | `EPOCHS=3 blockquant.py` |
| `blockscale_w994.json` | `blockscale.py` |
| `sweep_w994_mnist_{computed_b0,computed_b32,learned_b0}_3ep.json` | `FORMATS=TNF4 TASK=mnist EPOCHS=3 SCALE_MODE=… BLOCK=… sweep_w951.py` |
| `rung_w994_mnist_{computed_b0,computed_b32,learned_b0}_3ep.json` | `TASK=mnist EPOCHS=3 SCALE_MODE=… BLOCK=… rung964.py` |
| `rung16_w994.json` | `rung16.py` |
| `mac_w994.json`, `acc_w994.json` | `macrig.py`, `accrig.py` (the rigs write `*_w952.json`; renamed on copy) |
| `census_tnf8_w994.json` | `census963.py` |
| `mechanism_w994.json` | `python3 mechanism.py measurements` (reads the `stability*` records; TNF4 rows only from records marked `"tnf_grid": "trit-words"`) |

Not rerun, and so not current for TNF: the Fashion-MNIST and KMNIST arms (no data
on this machine); the TNF rows of the float-lane records `flane_w953.json` and
`curve_w955.json` (yosys 0.67 reports multiple drivers on those rigs); the TNF4
arms of the learned-scale LSQ records `lsq_2026-08-20.json` and
`lsq_width_matched_2026-08-20.json` (only the MNIST w4a4 arm, which is the
stability base configuration, was recomputed, as `stability_w994_mnist_gs_3ep.json`);
and the structural RTL records (`structural_w942`, `struct966`): that RTL
decodes the exponent rows above `offset_max` as numbers, which is a design
question for the RTL, not a rerun. The learned-scale rung
(`rung_w994_mnist_learned_b0_3ep.json`) is not bit-reproducible on this torch
build; two runs gave +0.024 and +0.038 points. The committed file is the second.
