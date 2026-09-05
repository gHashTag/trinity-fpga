# Ready-to-paste related-work subsection — measured, not asserted

> Produced 2026-07-31, **rewritten 2026-08-01 (pass 60)** after the network turned
> out to be reachable. The first version rested on one comparable and said so; this
> one surveys four, each measured from the artefact rather than from its own
> description.
>
> **Target:** Paper B, related work, as a short subsection.
>
> **What this does and does not claim.** Paper A's abstract already positions
> GoldenFloat against *format families* — posit, takum, OCP-MX, IEEE P3109. That
> gap does not exist. What no version of either paper does is position the
> **conformance corpus** against existing published *vector sets*, and that is what
> this supplies.

---

## Positioning against existing conformance material

Conformance testing for numeric formats is well established. What varies, and what
decides whether a third party can use the result, is the **form** it takes: a
committed table of bit-pattern → value that anyone can read, or a program that must
be compiled and run.

Measured from the four comparable projects:

| project | formats | ships consumable vectors | how it checks |
|---|---|---|---|
| **IEEE P3109 WG** (`github.com/P3109/Public`) | one parametric family, `binaryKpP`, K = 8…23 | **Yes** — **504 CSV tables, 154 MB**, exhaustive per configuration, exact hex-float values | published as reference material, and *explicitly disclaimed for conformance* |
| **Berkeley TestFloat** | 5 (binary16/32/64/80/128; *"cannot test decimal floating-point"*) | **No** — *"distributed in the form of ISO/ANSI C source code"* | differential against the SoftFloat reference implementation |
| **libtakum** (the takum author's C99 reference) | takum8/16/32/64 + log variants | **No** — 0 data files among 721 | round-trip self-consistency (`from_float64(to_float64(t)) == t`), expectations inline in C |
| **SoftPosit** (the posit reference) | posit8/16/32 | **No** — 0 data files among 156, no test directory | — |
| **microxcaling** (Microsoft, MX reference) | the MX formats | **No** — 0 committed data files over 4 KB among 80 | programmatic tests in Python |
| **numpy** | 2 (binary32, binary64) | **Yes** — 26,615 rows across 20 CSV files | fixed vectors with a stated **1–4 ULP tolerance** |
| **this corpus** | **83, across 13 families** | **Yes** — 5,075 vectors across 83 packs | fixed vectors, 4,949 at `abs_error = 0`; the remaining 112 disclosed via allowlist |

Three things follow, and the third matters most.

**The largest exact table set belongs to the standards body, and it may not be used
for conformance.** P3109's public repository publishes 504 CSV tables totalling 154
MB, exhaustive per `(K, P)` configuration, with rows of the exact shape a
conformance vector needs — `codepoint,value,subnormal`, values as exact hex floats
such as `0x1.8p-15`. Its README then says, in bold terms, that *"the contents of the
repository must not be utilized for any conformance/compliance purposes"*, because
they are unapproved drafts subject to change.

So the material exists and the field still has no citable conformance corpus for
these formats. That is a more precise statement of the gap than "nobody publishes
vectors", and it is the gap this work actually fills.

**Among implementations, distributed vectors remain rare.** Of TestFloat, libtakum,
SoftPosit and microxcaling — including the two written by the formats' own authors —
none ships a consumable table. A consumer wanting to check a takum implementation
today must compile libtakum and compare against it.

**Exactness here is a consequence of scope, not of superior rigour.** numpy's sets
cover transcendental functions, where correctly-rounded evaluation is not guaranteed
by any common libm, so a tolerance is the only defensible claim. TestFloat's own
author notes it is *"not especially good at testing difficult rounding cases for
divisions and square roots."* This corpus covers decode and encode, which is
decidable: an exact rational either is or is not the value of a bit pattern. The
right comparison is not "exact beats approximate" but "a decidable problem admits an
exact answer, and this is what one looks like."

That boundary is visible inside the corpus too. Its own `takum32` pack, checked
against libtakum, agrees bit-identically on 3 of 15 vectors and differs by **exactly
one ULP** on the other 12, never more — because a logarithmic decode needs `exp()`.
Three independent artefacts at very different scales mark the same frontier.

---

### Notes for whoever applies this

- The table is the load-bearing part. Every cell was measured: TestFloat's from its
  own distribution page, libtakum's and microxcaling's by counting file types in
  their repository trees, numpy's from
  `numpy/_core/tests/data/umath-validation-set-*.csv`, and this corpus's from
  `gHashTag/t27/conformance/vectors/INDEX_all_formats.json` (in the **`t27`** repository, `conformance/vectors/`).
- Keep the concession. numpy is deeper (26,615 vectors to 5,075) and covers 20
  operations this corpus does not touch. Stating that is what makes the 83-vs-5
  format comparison credible.
- **Do not generalise the table into "the first" or "the only."** Six comparables is
  a survey, not a census. What the table supports is "of the six projects measured",
  and nothing wider.
- **Not surveyed:** SoftFloat (TestFloat's reference implementation, examined only
  through TestFloat's description of it), and any vendor-internal vector set, which
  by definition cannot be checked.

  > An earlier version of this note listed SoftPosit as "not fetched" and P3109's
  > material as "not publicly available". Both were surveyed afterwards — SoftPosit
  > in pass 76, P3109 in pass 63 — and both are now *in the table above*, P3109 as
  > its lead row. The note had come to contradict the table it annotates, in the
  > paragraph warning against overclaiming.
- The last paragraph is the actual contribution: bit-exactness is attainable over
  the decidable class, and the corpus's own takum result locates the frontier from
  the inside. That is more useful to a reader than any novelty claim.
  (`specs/numeric/related_work_measured.t27`)
