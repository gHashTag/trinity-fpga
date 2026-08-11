# Two of tonight's four comparisons are below the harness's noise floor

Both rebuilt rungs were decomposed by building an unguarded twin of each, so the
$k$ change and the reservation cost separate. Then each pair was tested against
the five-seed spread rather than compared on medians.

| pair | median difference | seed ranges |
|---|---|---|
| TNF17e, guard vs none | **+10.3%** | 0.1176–0.1267 vs 0.1236–0.1332 — **overlap, not distinguishable** |
| TNF64b, guard vs none | **−11.1%** | 0.1111–0.1246 vs 0.0981–0.1100 — **separated, real** |

So the 17-bit "guard makes it faster" is **noise**, not the output-space-pruning
effect it looked like. The 65-bit guard cost is real.

## The methodological gap this exposed

`full_table.json` stored only median and spread per row. **A median and a spread
cannot answer whether two rows differ**, so none of this table's rankings had
ever been tested for significance — including the headline comparisons against
`binary16`.

Per-seed values are now stored for the seven rows measured in this session. The
remaining twenty rows hold medians only, and **every comparison involving them
is currently untestable.** Re-sweeping them to recover per-seed data is the
cheapest way to find out whether the ranking means anything.

## What this does to tonight's earlier claims

The 65-bit result stands: reducing $w(k)$ from 46.6% to 19.9% did not buy
throughput, and the guard costs a real 11.1%.

The 17-bit result — reported earlier as "+11.9% faster while also guarded" —
**cannot be decomposed and may not survive a significance test**, because the
E_t=4 rung it beat has no per-seed record. The claim is suspended, not
withdrawn: it needs the old rung re-swept before it can be stated either way.
