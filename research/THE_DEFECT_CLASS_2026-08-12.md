# One defect, eight times: the harness asserts less than its prose claims

Nine sweeps over two repositories found eight instances of a single failure and
two examples of the correct form. This is the consolidated record, because the
instances are currently spread across nine documents that each argue one point,
and the pattern is worth more than any of them.

## The eight

| # | the harness | its prose said | its code did | what it cost |
|---|---|---|---|---|
| 1 | `campaignA_books.check` | "T38 on **BOTH** tails" | `assert max(pos, neg) == 1.0` | a clipping arm at +1.000/−0.750 ranked as a *placement* for two campaigns; a published protocol finding withdrawn |
| 2 | `run_synth.py` | one Fmax per seed | appended **two** per run, sliced the last N | a median over three post-route and two post-placement figures |
| 3 | the decoder cost | "logic LUT" | counted `SLICE_LUTX` **BEL occupancy** | 1.00× reported where the truth was 1.67× |
| 4 | the render harness | "5 runs passed" | 5 × `exit=1` in 0 s, build directory absent | a setup failure nearly reported as flakiness |
| 5 | `campaignB_stats.row` | "POOLED OVER FOUR MODELS" | `np.concatenate` → t-test at n = 140 | **eleven of fourteen verdicts** flipped to TIE |
| 6 | `gate_status_ratchet` | "every gate" | globbed three prefixes in **one** directory | 102 gated scripts invisible — in an instrument written *the day after* the lesson was recorded |
| 7 | `audit_dsp_inference`, `audit_additional_cores` | aware of the block trap, comments naming it | never cross-checked the histogram against yosys' own declared total, which sat unused in the same dict | a silently-low LUT count, the exact shape of the retracted table their comments describe |
| 8 | the first log-parse detector | "finds parse-without-count" | matched label formatting and the canonical `exec(compile(_s.split(MARKER)[0]))` import | 96 hits, ~all false — an instrument that noisy is worse than none |

## The property they share, which is not "we didn't know"

**In every one of the first seven, the fact was already written down in the
repository, in prose, before the defect did its damage.**

* `campaignA_books.py`'s module docstring: *"TOP … renormalisation pays for by
  clipping the negative extreme to −0.75"*
* `campaignD_spearman.py:86` carried an explicit `without TOP (n=4)` column
* `SIXTEENTH_CODEWORD_SPENT.md`: *"**TOP is a trap.** … reach bought on one
  side, paid for by clipping on the other"*
* `website-checks.yml`'s header: *"The three checks that exist and never run"*
* `audit_additional_cores.py`: *"the trap that produced pass 250's retracted LUT
  table"*
* `run_all_gates.py`'s docstring named two defects that survived a pass because
  nothing ran everything

Three separate places recorded that TOP clips. The arm sat in the ranked pool of
every campaign anyway. **Prose does not execute.** Only the assertion is
load-bearing, and an assertion that is weaker than the prose above it is worse
than no assertion, because it reads as protection.

## Why it produces plausible numbers rather than crashes

A too-permissive check does not yield an obviously wrong answer. It carries an
ineligible member through the whole analysis and yields a **plausible** one. The
symptom is not a failure; it is an unexplained instability — which then gets its
own research campaign.

**Three campaigns here went into explaining an instability that was one
ineligible book in a pool of ten.** Five separate predictor failures turned out
to be one, and it was structural. That is the real cost: not the wrong number,
but the months of work spent explaining it.

## The two contrast cases, so "correct" is concrete

**`fpga/codebook/logic_count.py`.** Takes the final `stat` block *deliberately*
with the reason in its docstring; raises on a missing block; raises on a missing
cell table; raises on an unflattened submodule; and **cross-checks the histogram
sum against yosys' declared cell total**. Four ways to fail loudly. It produced
the published decoder LUT costs and they survived audit.

**`campaignB_selector.py:115`.** Sets its tolerance from *the smallest KL gap the
ranking must resolve*, not from a constant. A tolerance compared against a round
number is a tolerance nobody checked against the distinction it protects.

## The checks, in the order they cost least

1. **Read the expression, not the sentence above it.** Determine the exact set of
   inputs that passes. Ask whether that set is the one the prose describes.
   `max(a, b) == 1.0` is satisfied by *either*; `assert a == 1.0; assert b == 1.0`
   is the claim.
2. **Feed it one input that should fail.** Every one of the eight would have been
   caught in under a minute by a single deliberate bad input. A defect you cannot
   exhibit is a suspicion; a check you have never seen fail has unknown
   behaviour.
3. **Make a new gate's first act be to disagree with itself.** Run it twice on an
   unchanged tree under different load. That is how the gate ratchet's own
   wall-clock dependence was found — two "degradations" and one "improvement" on
   a tree nobody had touched.
4. **Before writing a gate, `grep` for the gate.** Three times the fix for "this
   is not checked" was already in the repository, uninvoked. *Not written* and
   *not run* look identical from outside and the second fix is one line of YAML.
5. **Bound the blast radius by imports — and remember what imports do not
   bound.** `run_asym.py` inherited a fix through `import run_synth`.
   `campaignB_stats.py` did **not** inherit one, precisely because it duplicated
   rather than imported — and the correction document used "it never called
   `check()`" as an *exemption* when it was the opposite.
6. **Watch the noise floor of your own detector.** #8 is on this list because the
   instrument built to find #1–#7 was itself the defect class: it claimed to find
   parse-without-count and mostly found string formatting.

## The one-line version

**Read what the assertion compares, not what the line above it says it
compares** — and then break it on purpose, once, before you trust it.

---

*Instances 1–8 are recorded in full in `research/block/CLIPPING_ARM_CORRECTION`,
`PLACEMENT_AND_ASYMMETRY`, `CODEBOOK_SILICON`, `POOLED_VERDICTS_RESTATED`,
`GATES_THAT_NEVER_RAN`, and the merge history of gHashTag/trinity#721. The
practice is §§8b–8h of `.claude/skills/measurement-discipline/SKILL.md`.*
