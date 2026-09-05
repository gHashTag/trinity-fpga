# The silicon table reproduces, its LUT column is exact, and its MHz column is not

Two findings, one correcting the previous iteration's suspicion and one
correcting the table.

## 1. The table is post-route and reproduces exactly -- my doubt was wrong

Iteration 13 recommended re-measuring the 21-format table because "it is all
from synthesis." That was wrong: `fpga/tnet/mk8.sh` runs `nextpnr-xilinx` and
greps `SLICE_LUTX` and `Max frequency`. The table was always post-route.

Reproduced today:

| format | published LUT | reproduced LUT |
|---|---:|---:|
| int8 | 448 | **448** |
| fp8 e4m3 | 490 | **490** |
| fp8 e5m2 | 481 | **481** |

Exact, to the LUT.

## 2. But the script had rotted, so nobody could have reproduced it

`mk8.sh` instantiates `gft_add_w`. The file `gft_add_w.v` defines
**`tef_add_w`** -- the TEF-to-TNF rename changed the module name inside and left
the script untouched. Yosys errors with "module not part of the design", no JSON
is produced, and every run reports empty.

The table was reproducible in principle and not in practice, from the rename
until now. **A reproduction path that is never run is a claim, not a
capability.**

## 3. The MHz column carries 11.4% placement noise; the LUT column carries none

Five placement seeds, same design, same constraints:

| seed | LUT | Fmax |
|---:|---:|---:|
| 1 | 448 | 85.76 |
| 2 | 448 | 78.06 |
| 3 | 448 | 76.98 |
| 4 | 448 | 80.67 |
| 5 | 448 | 80.94 |

**LUT spread 0.0%. Fmax spread 11.4%.**

The table's ordering metric is MHz per LUT, so it inherits the full 11.4%. That
covers the top of the table:

| rank | format | MHz/LUT | gap to leader |
|---:|---|---:|---:|
| 1 | int8 | 0.189 | -- |
| 2 | GFTernary | 0.177 | 6.3% |
| 3 | TNF4 | 0.167 | 11.6% |
| 4 | binary32 | 0.163 | 13.8% |

**Differences under about 11% are not resolvable from a single placement run.**
The ordering of the first four rows is therefore not established by the published
data, including the statement that `int8` leads GFTernary by 7%.

## What survives

The group separation does. Fixed fields against tapered ones is 2.4x to 6.4x,
far outside an 11.4% band, so the boundary the paper actually argues from is
unaffected. What is not established is the within-group ordering, which the paper
already declines to lean on -- now with a number attached rather than a
qualitative hedge.

## Theorems

**T (area is deterministic, timing is not).** Under a fixed netlist and
constraint set, placement seed variation leaves LUT count invariant and moves
achieved frequency by a bounded but non-trivial amount. Measured here: 0.0%
against 11.4% over five seeds.

**Corollary.** Any metric combining the two -- throughput per area being the
common one -- inherits the timing variance in full. A single-run ranking on such
a metric resolves only differences exceeding that variance.

**Practice adopted.** Report LUT from one run and frequency as a median over at
least five seeds, with the spread stated. Do not rank rows whose separation is
below the measured spread.

## Method note

This iteration set out to re-measure a table on the suspicion it used the wrong
instrument. The suspicion was wrong and the table was right. Two real defects
turned up anyway -- a rotted reproduction path and an unquantified noise floor --
neither of which was what the iteration was looking for. **Checking a claim you
believe is wrong is worth doing even when it turns out right.**
