# Ternary is forced by cardinality, not by identity

A literature pass reported that for base `phi` the minimal digit alphabet
permitting constant-time parallel addition is "exactly {-1, 0, +1}". If true it
would be the strongest single statement available here: the ternary alphabet
forced by a theorem rather than chosen. An adversarial check found the report
mis-stated in the one word that carries the weight.

## What the theorem says

Frougny, Pelantova and Svobodova, *Parallel addition in non-standard numeration
systems*, Theoretical Computer Science, 2011. The minimality is of
**cardinality**, not of the particular set. Three digits are necessary and three
suffice; `{-1, 0, +1}` is one alphabet of three that works, and it is not the
only one --- a working `{0, 1, 2}` parallel adder for base `phi` was constructed
and tested during the check, which refutes "exactly" directly.

**So the correct statement is: for base `phi`, parallel addition requires three
digits and admits three. Ternary is forced. The particular letters are not.**

That is weaker than the report and stronger than nothing, and it is the version
that goes in the paper. It says a two-letter alphabet cannot be made to work at
any window size, which is a real impossibility and not a design preference.

## The constant is not small

"Constant time" here means p-local: each output digit depends on a bounded
window of input digits. Their Algorithm III on `{-1,0,1}` is **21-local, with
memory 10 and anticipation 10**. A reader who takes "constant time" to mean
"cheap" would be wrong by an order of magnitude, and the paper should say the
number rather than the adjective.

## Scope, stated because it limits us

The theorem concerns the **digit alphabet of a positional representation**. Our
weights are a **weight alphabet** whose values are `{-phi, 0, +phi}` and whose
accumulator is a pair of integers that is never reduced to a canonical digit
string. The datapath therefore never performs the operation the theorem is
about. What transfers is the impossibility --- no two-letter alphabet supports
parallel addition in base `phi` --- and what does not transfer is any claim that
our specific alphabet is the unique one.

We had already recorded, from Berend and Frougny (1994) and Akiyama (2016), that
normalisation is finite-automaton realisable only for Pisot bases and that the
one-adder family leaves the Pisot set above degree 3. This is the same boundary
seen from the other side: the machinery the theorems describe is machinery our
datapath does not contain, which is why it runs at degrees where that machinery
provably cannot exist.

## Lind--Boyd, and a gain that is not free

The same pass established that the family `r^d = r + 1` is Lind's conjectured
smallest Perron number of degree `d`, corrected by Boyd (1985): the conjecture
fails exactly at `d > 3` with `d = 3, 5 (mod 6)`. Computed for `d = 2..16` the
exceptional branch is strictly smaller at exactly `d = 5, 9, 11, 15`, and the
roots reproduce Wu (2010) Table 1 for `d = 13..24`.

Two corrections came with it. "Disproved" overstates the history --- Lind's
conjecture was private correspondence and never published, so Boyd corrected an
unpublished conjecture rather than refuting a published claim. And **the
fineness gain is not free**: the exceptional winners cost more than one adder,
where the family costs exactly one at every degree. A finer rung at higher adder
cost is a different trade from a finer rung at the same cost, and only the
second would have been news.
