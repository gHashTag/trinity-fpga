# The weights directory vanished mid-campaign, and the recovery is the recipe

Every number in the block campaign was measured against a directory in `/tmp`
belonging to a *different session's* scratchpad:

    /private/tmp/claude-501/…/0e868af8-…/scratchpad/weights/
        smollm2/ qwen/ pythia/ opt/ gpt2/ wikitext2-test.parquet

It was there at the start of this session and gone before the end of it. The
session directory survived; the `weights/` subtree did not. Nothing in the
campaign records how to rebuild it, and eleven documents quote numbers that only
that directory could produce.

**This is the same class as the FPGA fleet note in the project memory — *a
configured fleet is a perishable measurement* — and it applies with more force
here, because a bitstream can be reflashed from a repo while a `/tmp` corpus
cannot be reconstructed from anything the repo contains.**

## The recovery, and why each step is load-bearing

1. **The corpus came back from the HuggingFace cache**, which is under `~` and
   survived: `datasets--Salesforce--wikitext/snapshots/*/wikitext-2-raw-v1/
   test-00000-of-00001.parquet` → `wikitext2-test.parquet`. 4,358 rows,
   1,294,336 characters joined with `"\n\n"`.

2. **The model came back from the Hub.** `HuggingFaceTB/SmolLM2-135M`,
   `safetensors` only.

3. **And neither of those is evidence of anything until the ruler reproduces.**
   A restored corpus that differs by one row, or a re-uploaded checkpoint with
   different weights, produces numbers that look exactly like the old ones and
   are not comparable to them. So:

   | | measured on the restored substrate | published | relative |
   |---|---:|---:|---:|
   | SmolLM2-135M fp32 | 14.4874 | 14.4874 | **1.65e-06** |
   | SmolLM2-135M MXFP4 | 21.9397 | 21.9397 | **1.74e-06** |

   **The gate passes.** The restored substrate is the same instrument, and
   measurements taken after the loss are comparable with those taken before it.
   Had it failed, every post-loss number would have been on a different ruler and
   the honest move would have been to say so rather than to quote them together.

## What this changes about how the campaign should record itself

The campaign has spent this week finding that its *harnesses* asserted less than
their prose claimed. This is the same defect one level down: **the substrate was
never pinned at all.**

Three things a measurement record needs and this one did not have:

* **A provenance line per input** — the exact Hub repo id and revision for each
  checkpoint, and the dataset repo, revision and file for the corpus. `gpt2` and
  `bigscience/bloom-560m` are not versions; `gpt2@<sha>` is.
* **A fingerprint that can be checked without the original.** The corpus's
  row count and character count are in this file; a content hash of the joined
  text belongs in the measurement records themselves, so a restored copy can be
  compared to what was actually used rather than to a description of it.
* **A ruler gate that runs on restore, not only on first use.** It exists —
  `lineC_fifth.py`'s G2 reproduces all four published pairs before touching a new
  checkpoint — and it is exactly what turned this loss from a campaign-ending
  event into twenty minutes. It should be the documented first step of any
  session that measures, not a gate one file happens to carry.

The general form, and it is the same sentence as everywhere else this week:
**a number is only comparable to another number if something checkable says the
instrument did not move.** The harness lessons were about assertions inside the
instrument. This one is about the instrument's inputs, which nobody had asserted
anything about at all.

---

*Recovery performed 2026-08-12. Ruler gate run in this session's own process:
SmolLM2-135M, 40 × 2048 windows, block 32, E8M0, `lm_head` excluded, both
published values reproduced to under 2e-06 relative.*
