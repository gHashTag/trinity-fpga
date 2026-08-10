# The rot was not one script

Iteration 14 found `mk8.sh` broken by the TEF-to-TNF rename and fixed it. The
obvious next question is whether it was the only one. It was not.

## Swept: every shell script in `fpga/` that invokes yosys

Eight scripts. Three stale references, in two distinct conditions.

**Rotted, load-bearing, fixed:** `fpga/tnet/mkgf.sh` instantiates `gft_add_w`
where the file defines `tef_add_w` -- the identical defect as `mk8.sh`, in the
script that produced the **GF rows** of the 21-format silicon table. Same rename,
same silence, same result: yosys errors, no JSON, empty output fields.

**Dead, not load-bearing:** `fpga/tef/upper/sweep.sh` and `upper.sh` instantiate
`tef_mul_wp` and read `tef_mul_wp.v`. That module exists nowhere in the tree
**and nowhere in reachable git history**. These are not rotted paths but paths
whose source is gone.

Checked before calling it harmless: the word "upper" in the paper refers to the
upper rungs of the ladder, not to these scripts, and no published figure traces
to them. The gate lists them separately for that reason -- conflating dead
tooling with a broken reproduction path would make the tree look worse than it
is.

## Theorem

**T (a rename is a whole-tree edit).** Renaming a module changes an identifier
that appears in two kinds of place: source files, which a compiler checks, and
build scripts, which nothing checks until they are run. If the artefact a script
produces has already been recorded, the script may never be run again, and the
break is invisible for as long as the artefact is trusted.

**Corollary.** The interval between a rename and its discovery is bounded below
by the interval between reruns of the affected script, which for a script that
produced a finished table is unbounded.

## The gate

`tools/check_script_rot.py` collects, for each shell script invoking yosys, the
Verilog files it reads and the module names it instantiates, and reports
instantiations with no matching definition. In CI on every push and pull request.

Negative-tested before being trusted: replacing a live instantiation with a
nonexistent name is caught, and the script is restored byte-identical afterwards.

## Count

This is the second defect of the same class found in two iterations -- and the
first was found by accident while trying to disprove something else. The class is
**an artefact that outlives its ability to be regenerated**, and it does not
announce itself, because everything downstream continues to work from the
recorded numbers.
