# Branch ledger

Pass 148 asked whether this campaign had been repeating itself and found that it had,
once: `specs/numeric/takum_variant_split.t27` sat on an unmerged branch for two days
while three later passes worked around its absence — two of them wrongly. The survey
that found it cost a full pass. This file exists so the next one does not.

**State after the pass-149 cleanup:** 72 remote branches → **5**, plus `main` and five
dependabot PRs. 57 local branches deleted. Every branch removed had a **merged PR**;
squash merges make `git branch --no-merged` over-report, so each was additionally
checked file by file against `main` before deletion.

---

## The five that remain, and why

| branch | commits ahead | decision |
|---|---|---|
| `fix-takum-negation` | 4 | **Harvested — do not merge as-is.** Its central file was recovered into `main` in [#336](https://github.com/gHashTag/trinity-fpga/pull/336) with a reconciliation header. The remaining three commits predate pass 146's retraction and describe the takum variant split in terms since superseded. Kept as provenance for the recovered spec. |
| `resolve-takum-contradiction` | 1 | **Do not merge.** Carries *"positive half 32,768/32,768 EXACT, negative half diverges — 32,766 of 65,536"*, measured against `takum<N>_to_float64`. Pass 146 established the corpus implements `takum_log<N>` and retracted exactly this result. Merging it would reintroduce a withdrawn claim. Kept as the record of what was withdrawn. |
| `trinet` | 32 | **Superseded.** The TRI-NET line reached `main` by other routes; `main` carries newer trinet commits than this branch. Kept until someone confirms nothing unique remains. |
| `tri-net-ternary-internet` | 116 | **Superseded**, same as above, and much older. The commit titles overlap work already in `main`. |
| `wave-loop-gfa-polyq-ablation-30e` | 1 | **Stopped line.** The wave-loop / farm work the user ended. Not to be resumed. |

Nothing here is scheduled for merge. Two are kept as evidence of retracted claims,
which is a reason to keep a branch and not a reason to merge it.

---

## How the survey was done, so it can be repeated cheaply

`git branch -r --no-merged origin/main` over-reports under squash merges — every branch
merged that way shows as unmerged, because its commits are not ancestors of `main`.
The reliable test is content, per file:

```
base=$(git merge-base origin/main "$b")
git diff --name-only "$base" "$b" | while read -r f; do
  git diff --quiet origin/main "$b" -- "$f" || echo "differs: $f"
done
```

A branch with zero differing files is fully contained in `main`. A branch with
differences is *not* necessarily unmerged work — usually `main` moved on and rewrote
the same files. To tell those apart, cross-check against GitHub's own record:

```
gh pr list --state merged --limit 400 --json headRefName --jq '.[].headRefName'
```

A branch whose PR merged is settled, whatever the diff says. Only the branches with
**both** differing files **and** no merged PR need reading. In pass 148 that reduced 72
branches to 5, and 5 to 1 that mattered.

---

## The blind spot that made it expensive

`research/audit_author_set_consistency.py` resolves citations with `git ls-files`,
which cannot see `git branch -r`. When it could not find `takum_variant_split.t27` it
recorded the file as `"NOWHERE -- flagged in the dossier"`. It was not nowhere; it was
one unmerged PR away, and that label made the gap look investigated.

The audit now searches remote refs and reports a citation resolving on a branch
differently from one resolving nowhere — because the fix is different. A missing file
needs writing; a file on a branch needs merging.
