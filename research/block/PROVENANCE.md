# Where the loose data files in this directory came from

`u_theory.py` writes one fixed filename, `u_theory_weights.json`, and takes the
model list from `argv`. So a run for a different model set overwrites the
previous one, and the way to keep both was to rename the output by hand. Two
such snapshots are in this directory. This file records what produced them,
because a renamed file has no generator and nothing else in the tree says which
command made it.

## `u_theory_weights_smollm2.json`

```
python3 research/block/u_theory.py weights smollm2
```

then renamed from `u_theory_weights.json`.

## `u_theory_weights_qwen_pythia_partial.json`

```
python3 research/block/u_theory.py weights qwen pythia
```

then renamed. `partial` because the default run is four models
(`smollm2 qwen pythia opt`) and this one covers two.

### How both attributions were established

Not from memory or from the filenames — from the data. Every record carries an
explicit `model` field, and the script emits 12 records per model (four block
sizes `K` × three formats `E2M1`, `E3M0`, `INT4`):

| file | records | models present |
|---|---|---|
| `u_theory_weights.json` | 36 | `pythia`, `qwen`, `smollm2` |
| `u_theory_weights_smollm2.json` | 12 | `smollm2` |
| `u_theory_weights_qwen_pythia_partial.json` | 24 | `pythia`, `qwen` |

Each count is exactly 12 × the number of models named inside it, and the names
match the suffix in every case.

Worth noting while here: **the live `u_theory_weights.json` is itself a partial
run.** It holds three models, and the script's default is four — `opt` is
missing from it. The filename does not say so; only the `model` fields do.

## `kurtosis_all.json` — no generator exists

**Nothing in this repository produces this file, and nothing reads it.** Stated
plainly rather than left to be rediscovered:

* `heavy_tail_test.py` computes kurtosis but only prints; it never opens a file.
* No script anywhere computes `kurtosis_blocknorm`, which is one of its three
  fields.
* Its `gpt2` entry carries a `note` tying the transposition convention to
  `lineC_fifth` G1, so it was made alongside that work — but `lineC_fifth.py`
  does not write it either.

The measurements look real — eight models, sample counts in the tens of
millions — and the script that produced them was never committed. It is recorded
in `tools/orphan_artefacts_baseline.txt` as accepted debt rather than given a
fabricated command here, because inventing provenance is worse than admitting
there is none.

Recovering or rewriting that script, or deleting the file, is a decision for
whoever ran it.
