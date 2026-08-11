# Our win over IEEE half depends on not checking the offset field

Iteration 85 reported rung A beating `binary16` by 14.7% at equal storage — the
first same-width win against IEEE in the catalogue. Iteration 86 measured that
it was not bought with code space (98.4% utilisation, not the 62.5% computed).

This iteration found what it *is* bought with.

## The unguarded decoder answers inputs the format does not define

Four trits name 81 offsets. The field holding them is seven bits and names 128.
The 47 remaining offsets are outside the format, and the decoder gives each a
distinct finite value — **24,064 codes in which a corrupted offset field is
indistinguishable from a valid one.**

Built the guarded version: a comparator on the offset, invalid → NaN. Verified
exhaustively: **41,472 of 41,472 in-spec codes exact, all 24,064 out-of-spec
codes flagged, zero errors.**

| rung A | LUT | MHz | MHz/LUT |
|---|---|---|---|
| unguarded | 502 | 69.87 | **0.1392** |
| offsets reserved | 549 | 64.86 | **0.1181** |
| | +9.4% | −7.2% | **−15.1%** |

`binary16` measures **0.1213**.

**The rung beats IEEE half by 14.7% while its invalid codes are undetectable,
and loses to it by 2.6% once they are detected.**

IEEE half needs no such check — all 65,536 of its codes are defined. The
comparison is between a format that must pay for a guard and one that has
nothing to guard.

## Proposition (the reservation cost)

If a specification covers $S \subsetneq C$, any implementation either **guards**
$C\setminus S$, paying the recognition logic, or **assigns values** to it, which
extends the specification to $C$. No implementation preserves both the
specification and the cost of the second.

## The dilemma this puts under the ladder

Either:

**(a) the exponent is ternary** — 37% of the word's codes lie outside the
format, the reservation cost is 15.1%, and the IEEE comparison is lost by 2.6%;

**(b) the exponent is a seven-bit binary field** — all codes are defined, the
14.7% win stands, but **the ternary structure this work is named for does not
reach 37% of its own code space.**

Both readings are defensible. They cannot both be used at once.

**We have no measurement that settles it. The paper now prints both numbers
rather than the one that flatters the result.**

## Also this iteration

The prose gate. Two nights running, this work published a property of the
silicon asserted from the specification. `tools/check_codespace_claims.py` first
tried to bind percentages to formats by nearest name in prose and could not — it
attributed rung A's own figure to `binary16` and flagged withdrawn figures
quoted inside their own retractions. **Guessing at prose does not work.** The
paper now marks live claims with `\codeuse{format}{percent}`; the gate verifies
each against `code_use.json` and *counts* the unmarked ones so drift is visible.
Five marked, all matching.

And a process note: two of five markup edits did not apply, silently, because an
earlier edit had changed the target string. **A patch by string replacement must
assert the file changed** — the repository's own gate says so, and I had not
done it.
