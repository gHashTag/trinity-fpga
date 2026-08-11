# Four of six reported decoder defects were the test, not the decoder

This work published six disagreements between a decoder and its reference.
Four are withdrawn. The decoders were correct; the comparison was not, in two
distinct ways, and neither way is detectable by the test itself.

## Way one: comparing an fp32 output against a real-valued reference

A decoder emits `fp32`. A reference names a real number. Requiring them equal
reports as error every code whose value has no `fp32` image --- a set fixed by
the two dynamic ranges and identical for a correct decoder and a wrong one.

For IBM hex32, range $16^{\pm64}$, that floor is **45.0%** of the code space.
The **28%** this work published lies entirely beneath it and carried no
information. Rounding the reference to `fp32` first moves the comparable set
from 22,001 to 30,245 codes.

## Way two: comparing against the wrong published variant

| format | implements | was compared against | reported | actual |
|---|---|---|---|---|
| takum16 | logarithmic, $(-1)^S e^{\ell/2}$ | linear, $(1+M/2^p)2^c$ | 98.7% | 632 / 61,505 |
| lns16 | scale 128 (`frac_bits=7`) | scale 256 (`frac_bits=8`) | 253 | 107 / 65,536 |

Both variants are internally consistent, so agreement --- the only signal a
conformance test has --- cannot separate "wrong decoder" from "wrong reference".
The variant has to be fixed by declaration outside the test. Each RTL stated its
variant in its header comment.

## What survived, and it is real

| format | well-posed result | verdict |
|---|---|---|
| IBM hex32 | 1,727 subnormals flushed to zero | **real defect, repaired** |
| VAX F | `exp_field==1` flushed to zero | **real defect, repaired** |
| posit16 | 4 codes at the extremes off by $2^2$ | **real defect, open** |
| posit32 | 48 codes | **real defect, open** |
| LNS16 | 3 zero/NaN convention + 104 sub-ulp | conformant, documented |
| takum16 | 632 at `fp32`'s denormal floor | conformant |

Both repairs cost what missing logic always costs: IBM hex32 went 687 → 1,008
LUT and 46.78 → 30.82 MHz; VAX~F went 527 → 560 LUT and 73.51 → 61.38 MHz,
falling from third place in the throughput table to below sixth. **A decoder
that omits a case is not fast, it is incomplete**, and this is the ninth and
tenth time that has been true in this work.

## The gate

`conformance/variant_map.json` binds each compared decoder to its reference
module and to a token that must appear in the decoder's own header;
`tools/check_variant_declared.py` fails if a declaration is missing or if map
and header disagree. Verified red by binding `lns16` to scale 256.

`conformance/wellposed.py` rounds the reference to the decoder's type before
comparing and excludes codes with no image.

## The shape

The instrument sat inside the failure domain it was measuring --- the same error
as diagnosing a network fault with a tool that runs over that network. A test
that could not be wrong about itself would have found two defects instead of
six, and the four false ones cost more attention than the two real ones.
