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
| `placer_router_full_2026-08-19.json`, `placer_router_sweep_2026-08-19.json` | 21 decoder designs x 3 placer/router configurations x 5 seeds, Fmax per seed, on xc7a200tfbg676-1. Produced by local nextpnr runs driven by `gen_placer_router_sweep.py` (which writes its raw `cfg_results.json` outside the repository); the two files here are the reduced tables copied in by commit 5f571f94. No script in the tree regenerates them, and the raw per-seed logs for these runs are NOT in the tree -- only the e2m11 arm has logs, in `pnr_logs/`. NOT the CI part (fbg484-2) and NOT a board measurement: the chipdb is an XC7A200T die in the FGG676 package, a combination no board of ours carries | current |
| `verdict_stability_2026-08-19.json` | derived from `placer_router_full_2026-08-19.json`: for each of 210 design pairs, in how many of five seeds design X beats design Y; 25 pairs unstable under heap/router1, max median margin 17.3%. Same provenance and the same two caveats as the file it is derived from | current |

Two earlier records are deliberately **not** copied here: an invariance record
whose harness tested representability against zero rather than against the range
bounds, and the pre-fix workload sweep taken with the same harness. Both are
superseded by the files above; the defect and its consequences are stated in the
paper rather than hidden.
