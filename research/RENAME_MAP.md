<!-- doc-refs: names-absent-files-by-design -->
# What the old names became

Forty-one references in our own research notes name files that exist nowhere.
They are not rot in the ordinary sense: the documents are accurate accounts of a
state the tree no longer holds, because the format was renamed twice and the
Russian-language paper line was retired.

Fixing them one by one would mean rewriting historical records to describe a
present they were not written about. Recording the map once lets a reader of any
of them translate, and leaves the records intact.

## The format renames

`GF-T` became `TEF` in commit `9e9286765` ("Rename GF-T to TEF here too, and gate
the prefix hazard that cost a spec"), and `TEF` later became `TNF` (Ternary
Network Floats). Any document written before those commits uses the earlier name
throughout, in prose and in filenames.

| named in an old document | what it is now |
|---|---|
| `gft16_ref.py`, `gft_ref.py` | `conformance/gfternary_ref.py` for the alphabet; `conformance/gf_ref.py` for the binary ladder |
| `gft_paper.tex` | `research/arxiv_tnf/tnf_paper.tex` |
| `tef_mul_wp.v`, `gft_add_w` -- absent from every tree | the TEF-era module names; the surviving RTL is under `fpga/tnet/` and `fpga/phiscale/` |
| `main_ru.tex`, `paper1-goldenfloat/main_ru.tex` -- absent from every tree | retired -- the Russian-language paper line was not carried forward |
| `ARXIV_UPLOAD_EN_v2.md`, `ARXIV_GFT16_v2.md` | superseded by `research/arxiv_tnf/` |

## The prefix hazard

The same commit gated a hazard worth restating: `gft*` as a glob prefix matches
both `gft16` and `gft_ref`, and a rename that treated the prefix as a unit
renamed things it should not have. Never glob a bare `gft` prefix.

## Sibling repositories

A reference resolving only in `t27`, `trinity-s3ai`, `claim-audit-lab`,
`tri-net`, `trios-mesh` or `zig-golden-float` is a real reference, not rot. CI
has no siblings in its checkout and cannot tell the two apart, which is why
`tools/check_doc_refs.py` counts them in its summary and writes them to
`tools/doc_refs_crossrepo.txt` rather than dropping them silently. Write such a
reference qualified -- `t27:specs/fpga/mac.t27` -- so a reader knows which tree
to look in.
