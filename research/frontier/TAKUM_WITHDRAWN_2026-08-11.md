# Withdrawn: takum16 is not 98.7% wrong, and the error was ours

Two iterations ago this work reported that takum16's decoder disagrees with its
reference on $64{,}688$ of $65{,}536$ codes, and put that in the paper. The
claim is withdrawn. The decoder is correct and the comparison was not.

## What happened

There are two takum formats. Hunhold defines a **linear** takum, whose value is
$(1+M/2^p)\,2^{c}$, and a **logarithmic** one, whose value is
$(-1)^{S}e^{\ell/2}$. The repository has a reference for each --- `takum_ref.py`
and `takum_log_ref.py` --- and the RTL states in its own header which it
implements: *value $= (-1)^S \exp(\ell/2)$*.

The comparison used the linear reference against the logarithmic decoder. Both
were right about different formats, and the $98.7\%$ was the distance between
them.

Against the logarithmic reference, evaluating its symbolic $e^{p/q}$ values:

| | codes | mismatches |
|---|---|---|
| against `takum_ref` (linear) | 65,536 | 64,688 |
| **against `takum_log_ref`** | **61,505 in fp32 range** | **632** |

The remaining 632 are at fp32's denormal floor: the table saturates at
$1.401\times10^{-45}$, the smallest fp32 denormal, where the reference gives
slightly larger values. That is the storage rounding, not the decoder.

**takum16's decoder is correct.**

## What survives, and it is a different finding

The synthesis report shows takum16 inferring **57 RAMB36 tiles**. Its $789$
LUTs are the glue around a $65{,}536$-entry block-memory table, and the
throughput column shows LUTs only.

**Comparing a format that spends 57 block RAMs against formats that spend zero,
on a LUT count alone, is not a comparison.** The table needs the memory column,
and that is the real defect this investigation found --- not in the competitor's
decoder, in our table.

## The shape of the mistake, since it is one this work has made before

A comparison is meaningless unless both sides are the same thing, and this is
the third time the two sides were not: TNF pre-widened against competitors
unpacked, a harness observing eight bits against one observing thirty-five, and
now a logarithmic decoder against a linear reference. Each time the numbers were
individually correct.

**Before quoting a disagreement, check that both sides name the same object.**
The RTL said which variant it implemented, in its second line of comment, and
reading it would have cost nothing.
