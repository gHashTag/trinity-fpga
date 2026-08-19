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
