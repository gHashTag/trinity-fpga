# Three theorems about pair checks, from a registry that passed while broken

A pair of artefacts that must agree was guarded here by a check comparing the
set of registered files against the set of files on disk, in both directions.
It passed. Meanwhile the registry held two different cases under one
identifier, and had not been valid YAML since the previous day's edit.

Both failures were invisible to the pair check, and for the same reason.

## T22 -- a pair check is blind to its own join key

A pair check compares two sets. Sets are joined on a key, and a set comparison
never looks at the key. If the key can collide, both directions of the check
can pass while the pair is incoherent: side A asks "is this file registered",
side B asks "does this row have a file", and neither can ask "does this
identifier name one thing".

Six collisions were live: five draft identifiers duplicating registry
identifiers, which would collide at graduation time, and one duplicate inside
the registry itself.

This is the doctrine's rule "identity before shared medium" (CLAUDE.md 5),
which was written from twenty hours lost to duplicate hardware addresses on a
shared bus. The rule was filed as a networking rule. It is not one. A duplicate
identifier in a shared namespace poisons every test downstream, including tests
of correct fixes, whether the medium is an Ethernet segment or a YAML file.

## T23 -- a regular expression cannot report that a file is malformed

An instrument reading a structured file with regular expressions cannot fail on
structure, because a regular expression sees lines. It parses a broken document
exactly as happily as a good one. Every check that had ever been run against
this registry read it with regular expressions, so the day the registry stopped
being YAML, nothing changed in any report.

This is the broken-ruler error with the failure inside the measuring instrument
rather than the measured system, and it is the sharpest instance yet found:
the ruler did not merely lie, it could not express the sentence "this is not a
ruler".

**Corollary (ordering).** Layers of a check are not interchangeable, and are not
a matter of taste. Each is a precondition for the next being meaningful:

    1. FORMAT -- the file parses at all
    2. KEY    -- identifiers are unique in every namespace that will merge
    3. SETS   -- the two sides agree, and declared counts match reality

A set comparison run on a file that does not parse reports nothing about the
sets. It reports nothing at all, in a shape that looks like a report.

## T24 -- a negative test matching on text conflates two failures

The first negative test for the repaired gate grepped its output for the
expected message and reported "missed" for five of seven layers. The gate had
in fact failed on every one -- earlier, at the format layer, because the
baseline the test restored from was itself corrupt. A negative test matching on
a failure message cannot distinguish *did not fail* from *failed differently*,
and the second reading is the more dangerous one, because it means the fixture
is broken and every result from it is void.

A negative test must assert the exit code **and** the cause, and must restore
from a baseline it has verified rather than one it merely saved.

## What was repaired

Five of the six defects were ours, all from the previous day: an entry added at
the wrong indentation level, which broke the document; that entry reusing an
identifier already taken; five drafts colliding with registry identifiers. The
sixth predates us -- a case registered in June whose write-up was never begun,
now declaring `file_status: not-written`, so an unkept promise is a recorded
state rather than a silent gap.

Seven negative tests, one per layer and per defect class, all failing on their
own cause.
