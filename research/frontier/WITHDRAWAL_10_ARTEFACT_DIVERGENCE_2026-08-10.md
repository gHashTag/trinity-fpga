# Withdrawal 10: the oracle and the RTL implement different formats under one name

Found by continuing withdrawal 9's systematic sweep into the silicon numbers.

## The divergence

| artefact | Et | M | word | binades | source |
|---|---:|---:|---:|---:|---|
| oracle / SSOT | 6 | 9 | **20 bits** | 729 | `gHashTag/t27/specs/numeric/formats_catalog.t27`, `tnf_ref.py` |
| RTL | 4 | 8 | **16 bits** | 81 | `fpga/tnet/bnf_decode.v` |

One label, two formats. The paper's accuracy figures describe the 20-bit one and
its silicon figures the 16-bit one, and it presents them as a single row.

The RTL is the correct artefact here: its comment reads "4 trits packed into 7
bits", so packing was applied there and not in the oracle. The two diverged and
nothing compared them, because every existing check verifies an artefact against
**itself** -- the oracle round-trips, the RTL simulates, the catalogue validates.

## And the BNF/TNF result reverses

The same RTL file asserts "TNF: a ternary field of **the same capacity**". It is
not:

| | field | exponent values |
|---|---:|---:|
| BNF16 | 7 bits | **128** |
| TNF16 | 7 bits (4 trits) | **81** |

**36.7% less**, with 47 of 128 codes unreachable. So "BNF16 and TNF16 land within
1% in placed silicon, confirming T6" compared fields of unequal capability.
Matching area at 36.7% less range is not a confirmation that the encodings cost
the same -- it is TNF paying capacity for that area. The interpretation reverses.

## Theorem

**T (artefact divergence).** If a specification is written in one unit and its
implementation in another, both artefacts can pass their own checks while
describing different objects. No within-artefact test detects this: it requires a
test **between** artefacts, comparing declared parameters rather than observed
behaviour.

## The gate

`conformance/check_artefact_agreement.py` compares catalogue parameters against
RTL parameters and flags three classes: declared parameters that do not fit
declared storage, parameter divergence between artefacts, and a ternary field
claiming the capacity of its binary sibling.

It reports **12 disagreements** on the current tree: nine catalogue rows whose
widths are wrong, two parameter divergences for `tnf16`, and the capacity
mismatch.

Negative-tested before being trusted: correcting `GF-T16`'s declared width to 20
makes exactly that line disappear, and the catalogue is restored byte-identical
afterwards. Parametric families that declare no width, and GFTernary which is an
alphabet rather than a float, are exempted explicitly rather than passing by
accident. The RTL-to-catalogue name mapping is written out, because the rename to
TNF changed display names but not ids -- a lookup that missed silently would have
made the gate report nothing, which is the failure mode the file exists to
prevent.

## Running count

Ten withdrawals. Nine and ten both came from the rule adopted after eight:
carry a correction to every claim resting on the same quantity. That rule has now
produced the two deepest findings of the night on consecutive iterations, which
suggests it is not exhausted.
