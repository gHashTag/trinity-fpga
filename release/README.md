# TNF — Ternary Network Floats: paper, data, and the instruments that check it

A self-contained snapshot: the paper, every data file its numbers are read
from, the gates that check it against itself, and the scripts that produced the
block-axis measurements.

**Source of truth is the repository**, not this archive:
`github.com/gHashTag/trinity-fpga`, branch `tnf-recovery-2026-08-11`.

---

## 1. Just read it

    paper/tnf_paper.pdf          89 pages

`paper/tnf_paper.tex` is the source; the seven `tnf_*.pdf` figures beside it are
the ones it includes.

## 2. Rebuild the PDF

Needs [tectonic](https://tectonic-typesetting.github.io) (no TeX install
required — it fetches what it needs).

    cd paper && tectonic -X compile tnf_paper.tex --outdir .

## 3. Check the paper against itself

Eight gates, each of which **exits non-zero on failure**. Run from the archive
root:

    for g in verify/check_self_consistency.py \
             verify/check_withdrawn_live.py \
             verify/check_latex_hygiene.py \
             verify/check_overfull.py \
             verify/check_exponent_window.py \
             verify/check_ladder_units.py \
             verify/check_conformance_counts.py \
             verify/check_codespace_claims.py; do
      python3 "$g" >/dev/null 2>&1 && echo "OK   $g" || echo "FAIL $g"
    done

They expect the layout `research/arxiv_tnf/tnf_paper.tex`, `conformance/`,
`tools/` — i.e. the repository, not this archive. **Run them there.** They are
included here so the archive documents what was checked, and with what.

### Two of the tools are REPORTS, not gates

`verify/check_paper_numbers.py` and `verify/check_scoped_superlatives.py` end in
an unconditional `sys.exit(0)`. **They cannot fail.** They were counted among
"gates green" for thirteen iterations before that was noticed. Read their output;
do not read their exit code.

`check_paper_numbers` currently lists **51 literals in the paper with no source
in any data file**. Some are constants derived in place; some are real provenance
gaps. That list is work, not noise.

## 4. Check the checkers

    python3 verify/mutate_gates.py

Injects into the paper the defect each gate exists to catch — **twice**: once in
the phrasing the gate was written against (a **control**, which must FAIL) and
once in an equally ordinary alternative (a **test**; if it PASSES, the gate has a
hole). Restores every touched file by bytes and purges `__pycache__` afterwards.

**Three holes are open** as of this snapshot, and `verify/GATE_AUDIT_2026-08-12.md`
records them and the five already fixed:

| gate | evading form | status |
|---|---|---|
| `check_overfull` | a **vertical** overflow (`Overfull \vbox`) | open |
| `check_ladder_units` | `UNIT: str = "..."` — annotated declaration | open |
| `check_codespace_claims` | `\codeuse{X}{ 62.5 }` — spaces in the braces | open |

## 5. Re-run the measurements

    measure/verify_block_rmse.py            block-axis RMSE, four arms
    measure/verify_block_ppl.py [models]    wikitext-2 perplexity
    measure/encoder_share_both_metrics.py   encoder share, both metrics
    measure/exponent_mechanism.py           lattice exponent vs corner density
    measure/codebook_exponent.py            four 4-bit codebooks
    measure/codebook_exponent8.py           three 8-bit codebooks
    measure/sensitivity_scope.py            S2 across models and encoders

**These need model weights, which are NOT in this archive** — they are several GB
of `safetensors` plus `wikitext2-test.parquet`. Each script carries the path it
expects at the top (`W = ...`); point it at a directory holding `smollm2/`,
`qwen/`, `gpt2/`, `pythia/` and the parquet. Requires `numpy`, `torch`,
`safetensors`, `transformers`, `pyarrow`.

`measure/PREREG_*.md` are predictions **committed before** their measurements ran;
the matching `*_RESULT.md` score them. Read them as a pair — the value is in which
ones failed.

---

## Status, stated plainly

🛑 **The paper does not publish until TNF beats MXFP4 on the block axis by
measurement.** As **written**, that rule is met: on the squared-error axis
`2^(k/3)` beats MXFP4's own best encoder by 14.1% with zero losing blocks in 14.9
million, and on perplexity by 7.2–12.4% across four models, each figure carried by
two independently written instruments.

As **intended** — "the world's number one format" — it is **not** met, and the
paper says so in its own text:

- The gain is **100% scale resolution**, not algebra.
- A **binary** ladder (`2^(k/8)`) realises it better than the ternary one, on both
  metrics and all four models.
- Of the headline against MXFP4's *reference* encoder, a large share is the
  baseline's **own encoder**, and that fix emits a byte-legal MXFP4 bitstream.
  On two of four models that share is **negative**.

**Sixteen of the paper's own claims are retracted in place.** The count is
checked by a gate, and the gate's counter had to be fixed twice for missing
retractions written in the active voice.

## The four formats

**TNF · BNF · GF · GF-T** — two axes, base and derivation. Each is distinct and
each is kept; formats that cannot train alone are listed in a separate rejected
table rather than dropped.
