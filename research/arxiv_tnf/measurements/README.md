# Measurement records backing the TNF paper

Most files here are machine-written records produced by a script in this
repository, copied verbatim under a dated name. Not all: one record was
transcribed by hand and six carry fields no script in this tree writes. They
are named under [Provenance of campaign records](#provenance-of-campaign-records)
rather than covered by a sentence that is not true of them.

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

## What this table covers, and what it does not

The rows above are the records that back a *named table or figure in the paper*.
They are a small part of the directory: the rest are records from the wider
campaign, kept because deleting a measurement to tidy an index is how a directory
starts disagreeing with what was actually run. The table is therefore **not a
listing of this directory**, and no number for the ratio is written here, because
a number written here is a number that goes stale. Ask instead:

```
python3 - <<'EOF'
import os, re
md = open("README.md").read()
named = set(re.findall(r"`([A-Za-z0-9_.\-]+\.(?:json|py))`", md))
here = {f for f in os.listdir(".") if f.endswith((".json", ".py"))}
print("%d of %d files carry a row" % (len(named & here), len(here)))
print("named but missing:", sorted(named - here) or "none")
EOF
```

The second line is the one that matters. A file this table names and the
directory does not hold is a broken index; a file the directory holds and this
table does not name is simply a record that backs no published figure.

## Provenance of campaign records

The orphan-artefacts gate (`tools/check_orphan_artefacts.py`) asks of every
record whether code produces it. For the records below the answer was never
written down, so the gate counted them as written without a script. Some were;
most were not. Each row says which.

A script writes under its own name and the record was copied here under a dated
one, so the second column gives both. `T27_WORK` defaults to the script's own
directory.

| record | producer and the name it writes | status |
|---|---|---|
| `oracle_rtl_2026-08-20.json` | `research/arxiv_tnf/oracle_rtl.py` -> `$T27_WORK/oracle_rtl/oracle_rtl.json` | generated |
| `structural_2026-08-20.json` | `research/arxiv_tnf/structural.py` -> `$T27_WORK/structural/structural.json` | generated |
| `stability_2026-08-20.json` | `research/arxiv_tnf/stability.py`, `TASK=mnist EPOCHS=3`, `INIT_PCT` unset -> `$T27_WORK/stability_mnist_gs_3ep.json` | generated |
| `stability_pct_init_2026-08-20.json` | the same, with `INIT_PCT=0.999` (the percentile recipe of `docs/FALSIFY-ME.md`) -> `$T27_WORK/stability_mnist_pct0.999_3ep.json` | generated |
| `stability_kmnist_2026-08-20.json` | the same script, `TASK=kmnist EPOCHS=3`; `INIT_PCT` not recorded (below) | generated |
| `stability_mnist_10ep_2026-08-20.json` | the same script, `TASK=mnist EPOCHS=10`; `INIT_PCT` not recorded | generated |
| `stability_mnist_30ep_2026-08-20.json` | the same script, `TASK=mnist EPOCHS=30`; `INIT_PCT` not recorded | generated |
| `stability_fashion_10ep_2026-08-20.json` | the same script, `TASK=fashion EPOCHS=10`; `INIT_PCT` not recorded | generated |
| `stability_fashion_30ep_2026-08-20.json` | the same script, `TASK=fashion EPOCHS=30`; `INIT_PCT` not recorded | generated |
| `placer_router_sweep_2026-08-19.json` | per-seed Fmax from `gen_placer_router_sweep.py` -> `$T27_WORK/cfg_results.json`; the spreads, `note` and `finding` were added by a step that is not in this tree | partly generated |
| `placer_router_full_2026-08-19.json` | the same sweep over all 21 designs; `inversions`, `inversion_pairs`, `note` and `finding` come from a step that is not in this tree | partly generated |
| `decoder_seed_spread_2026-08-19.json` | per-seed Fmax from `gen_decoder_seed_spread.py` -> `<scratchpad>/fmax_results.json`, a path hard-coded to the session that ran it; `spread_min_pct`, `spread_max_pct`, `note` and `finding` come from a step that is not in this tree | partly generated |
| `decoder_full_observation_2026-08-19.json` | the same driver over the full-observation harnesses, `gen_decoder_full_observation.py` (reads `wmap.json`) -> `<scratchpad>/wmax_results.json`, the same hard-coded path; `control`, `entries_below_control`, the spreads and `finding` come from a step that is not in this tree | partly generated |
| `decoder_cost_2026-08-20.json` | the LUT(N) fits from `fpga/tnet/gen_replicated.py` (its `generated_by` field) -> `$OUT/fit.json` (`OUT` is its second argument, default `/tmp/rep`); `method`, `metric` and `caveats` are not written by that script | partly generated |
| `verdict_stability_2026-08-19.json` | **no generator in this tree.** Its `method` field states the computation | not reproducible from the tree |
| `hardware_scan_2026-08-20.json` | **no generator.** Transcribed by hand from a read-only `openFPGALoader` JTAG scan, as its own `measured_by` field says | hand-written |

Three things a reader would otherwise have to find out the hard way:

- **The stability records do not record `INIT_PCT`.** `task`, `seeds` and
  `epochs` are in the file; the quantiser recipe is not, so the max-scale and
  percentile runs of the same task are told apart only by the filename, and
  for the KMNIST, Fashion and longer runs the filename does not say either.
- **`verdict_stability` cannot be recomputed from `placer_router_full`.** It counts,
  seed by seed, how often design X beats design Y, but `placer_router_full`
  stores each `fmax_by_seed` list **sorted**, so which value belongs to which
  seed is gone. Recomputing from those lists gives 22 unstable pairs for
  `heap/router1`, not 25.
- **`verdict_stability` disagrees with itself.** Its `configs` count 25, 27 and
  37 unstable pairs of 210; its own `finding` says "20-34". The commit that
  added it says 20, 23 and 34. The paper quotes none of these figures, so
  nothing published depends on which is right, but the record cannot be cited
  until it is regenerated from per-seed data.

