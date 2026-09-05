# GF+8 was measured with its selector tied off, and this one is ours by construction

Five modules in a row had turned out not to be their format once a reference
existed. GF+8 stood at rank three with no reference, so it was the obvious next
candidate. It failed differently, and for a reason that is entirely mine.

GF+8 is an **adaptive container**: a two-bit header selects one of four pockets
--- a $\varphi$-split $e3m4$, a narrow-exponent $e2m5$, an $int8$, and an $lns8$
--- and the module's own header says what the measurement is for: *"the area of
this mux plus four paths is the subject, against a single fixed decoder."*

It was measured with `pocket` tied to `2'b00`. Synthesis pruned three of the
four pockets and the multiplexer with them.

| GF+8 | LUT | $F_{\max}$ | MHz/LUT | rank |
|---|---|---|---|---|
| selector constant, as measured | $510$ | $72.84$ | $0.1428$ | **3** |
| selector live, the container | $628$ | $63.05$ | $0.1004$ | **17** |

Twenty-three percent more area, thirteen percent less frequency, thirty percent
off the ratio. The container costs what its own comment said it would cost, and
the number in the table was one pocket.

## Two further reasons that row should not have led

The module's header also carries `[prep для LUT-замера] НЕ Tier-E: до
UART-прогона на AX7203` --- *preparation for a LUT measurement, not Tier-E,
pending a UART run on the board*. **It declares itself unverified in its first
three lines**, and nothing in the paper's text discusses it: the row was its
only appearance.

## The sixth of a kind, and the first I caused

The previous five diverged because an artefact and its specification drifted
with nothing comparing them. This one diverged because **the measurement tied
off an input that the thing being measured exists to exercise**, and that is a
harness defect of the same family as observing eight bits of a thirty-five-bit
accumulator --- which this project has now made twice.

The rule that would have caught it: *a constant driven into a device under test
is a claim that the constant does not matter, and that claim needs checking.*
Both times the claim was false and both times the error flattered the number.
