# Pipelining does not rescue the non-closed path -- it hits a ceiling

The measured cost of non-closure carried a caveat we wrote ourselves: part of
the frequency gap is combinational depth, 46 dependent stages against one
addition, and pipelining converts depth into latency and registers rather than
removing it. An unclosed caveat in a paper costs more than a new theorem, so
this closes it by measurement.

The normaliser was regenerated as an S-stage pipeline, oracle-checked (56/56,
sum and the no-two-adjacent-digits property, at a latency of exactly S cycles),
and swept.

## 16-bit

| stages | LUT | FF | Fmax (median of 5) | latency |
|---|---|---|---|---|
| 2 | 1589 | 154 | 23.38 | 2 |
| 4 | 1473 | 168 | 47.38 | 4 |
| 8 | 1418 | 223 | 96.42 | 8 |
| 16 | 1436 | 279 | 141.00 | 16 |
| 24 | 1427 | 458 | 240.21 | 24 |
| 32 | 1428 | 456 | **249.44** | 32 |
| **closed** | **182** | **128** | **299.94** | **1** |

## 32-bit

| stages | LUT | FF | Fmax (median of 5) | latency |
|---|---|---|---|---|
| 2 | 6856 | 243 | 8.64 | 2 |
| 8 | 5937 | 382 | 36.50 | 8 |
| 16 | 5634 | 629 | 76.05 | 16 |
| 32 | 5579 | 848 | 106.12 | 32 |
| 48 | 5576 | 1584 | **111.36** | 48 |
| **closed** | **283** | **192** | **239.35** | **1** |

## The ceiling, and why there is one

Frequency rises with depth and then stops: 249 MHz at 16 bits, 111 MHz at 32.
Adding stages past that buys nothing, and at 32 bits the plateau is **less than
half** the closed path's single-cycle frequency.

**T30 (the normalisation floor).** A normalisation cascade cannot be pipelined
below one compare-and-subtract per stage, so its clock period is bounded below
by the carry latency of a compare-and-subtract at the datapath width. A
compare-and-subtract is strictly more than an addition -- it is a subtraction
plus the comparison that selects it -- so the floor of a non-closed path lies
above the floor of a closed one, whose step is a single addition. Depth can
approach that floor and cannot pass it.

So the trade is not frequency against registers. It is:

- **area**: 1428 against 182 LUT (7.8x) at 16 bits, 5576 against 283 (19.7x) at 32
- **registers**: 456 against 128 (3.6x), 1584 against 192 (8.3x)
- **latency**: 32 cycles against 1, 48 against 1
- **and still slower**: 249.44 against 299.94 MHz, 111.36 against 239.35

The caveat is closed in the direction opposite to the one that would have
weakened the claim. Pipelining was the strongest available objection and it
does not survive its own measurement.

## What the sweep also showed

Area *falls* slightly as depth rises -- 1589 to 1428 at 16 bits -- because
shorter combinational runs let the mapper pack more tightly. It is a real
effect and it is small; nothing about it moves the comparison.
