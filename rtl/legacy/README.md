# Deliberately defective wrappers, kept because they are the only reproducer

These are the pre-W984 wrappers, frozen at commit `6ae9296ff`. **Two of their four
clauses fold to a constant at synthesis** (T836), which is a defect, and they are
kept *because* of it.

For six waves -- W842, W977, W981, W982, W983 -- this project's one reproducible
hardware anomaly was read off these files: one netlist, several placements, more
than one answer. W984 repaired the folding across the corpus, and the anomaly
**stopped reproducing**: eight placements across the two repaired designs, all
`1111` (T841).

That is a good outcome for the corpus and a bad one for the investigation. The
repaired designs are 43 % and 121 % larger, so "the failure is gone" and "the
failure is absent in a design this different" cannot be separated -- and without a
case that fails, neither can ever be tested again.

So these stay, out of the corpus and out of `tri audit`'s clause gate, as the
regression case for the openXC7 report. **Do not fix them.** If you need an honest
measurement, use the wrapper in `fpga/verilog/`; if you need the anomaly, it is
here.

| file | folded clauses | die words it produced |
|------|----------------|-----------------------|
| `gft_dup_folded_jtag.v` | `c_init`, `c_self` | `1111` at seeds 1/42/31337, `1101` at 7/1234 |
| `gft_smul_folded_jtag.v` | `c_zero`, `c_gold` | `1010` (W977) |
