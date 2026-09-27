# Agent Wars: paid-by-result loop + GPU contributors (design, 2026-09-26)

Author: session notes for Dmitrii Vasilev (gHashTag). Status: draft for discussion.

## The economic core (owner's model, restated)

A task stays in the loop until it is SOLVED. Payment only for a result the
compiler accepts. The task is broadcast to every node in the network — FPGA,
GPU, CPU, hosted LLM bee — and the first node whose answer passes the judge
takes the reward. Everything else burned zero and earned zero.

This is a race market, not an hourly wage:

    QUEEN: issue (spec hole) -> broadcast to all lanes
    every lane runs its worker on its own hardware:
      bee (provider LLM) | IGLA on GPU | IGLA tern_tc on CPU | tern_tc on FPGA
    judge: t27c test-report (the compiler IS the referee, it cannot be bribed)
    first PASS -> reward (XP, non-transferable TRI credit) -> issue closes
    everyone else: nothing, log the attempt as an episode

Why this is honest: the judge is `t27c test-report`, the same binary a human
reviewer runs. A pass means "compiles and passes the spec's own tests" —
the merge-gate bar. No judge API, no subjective scoring, no way to argue.

## How the compiler is wired into the game today

- Queen shell: `apps/website/src/pages/Queen.tsx` + HUD views
  (`src/components/queenHud.ts`): comb, specs, kanban, map, factory, research,
  skills, crons, agents, functions, tools, project, tri, lanes.
- Review lifecycle: `src/pages/queenReviewLifecycle.ts` — a turn goes
  submitted -> reviewed -> accepted; acceptance credits XP (100/issue).
- The judge is the compiler: merge-gate structural checks run the spec's own
  tests via t27c (nightly, and per-turn on the worker side).
- Result display: the public board / activity endpoints feed the comb cells
  (Babylon hive): red = unresolved goal, blue = work/review, honey = done.

## What to strengthen: make the judge a first-class game object

1. **Judge replays as spectacles.** Every turn stores the t27c report (already
   produced). The wars view should render a turn as: candidate -> compile ->
   per-test pass/fail timeline. A kill-feed of "bee X failed test 3 of spec
   N, board Y passed" is the natural drama of a compiler-judged game.
2. **Compile-streak ladder.** compile@1 is our models' bottleneck (12-32%).
   Make it a visible stat: "this lane's worker compiles 31% of attempts",
   like a batting average. It turns training progress directly into a
   scoreboard movement the owner can watch.
3. **Same-seed duels.** When two lanes answer the same issue, show the two
   candidates side by side with their test timelines. This is the A/B the
   fp-vs-ternary pair gives us for free once IGLA lanes exist.
4. **Reward only on PASS, but credit partial progress.** distill the t27c
   report into XP-lite: compile-only attempts earn 1 XP (they are real work —
   our own data shows compile is 10x harder than parse). Pass earns 100.
   This keeps losers in the game and produces labelled training data:
   every failed attempt is a (spec, wrong-body, compiler-error) triple —
   exactly the fine-tune corpus IGLA needs next.

## GPU/CPU/FPGA contributors: the lane contract

Anyone with hardware joins as a lane, not as a miner:

    join  -> register lane {hardware class, worker id, PUBLIC_KEY}
    work  -> pull an open issue, run worker, submit candidate + t27c report
    earn  -> first PASS takes the reward; compile-only earns 1 XP
    proof -> the report is produced by the lane's own t27c; the board
             re-runs the judge on acceptance (trust but verify)

Training pipeline fits the same shape: an issue class "train" pays for a
better checkpoint (validated bits/byte or pass@k improvement measured by the
board, not self-reported). A GPU owner then earns by contributing compute to
the swarm's own model — the exact loop we ran this week on RunPod, opened to
third parties. Payment-on-accepted-result maps 1:1 to mint-on-acceptance
(V1 attestor quorum): the board is the attestor, the compiler is the oracle.

## FPGA lane specifics

- tern_tc fits XC7A200T block memory (6.46M ternary block weights = 77%
  BRAM); KV cache in DDR3. First milestone: one real tc layer matvec on the
  board, bit-equal to the CPU golden model (c_infer/tc_infer is validated to
  4e-6 NLL against PyTorch).
- A board lane is slow per token but ~free per watt; in the race market it
  wins the issues nobody else wants: long-tail specs where LLM bees idle.

## Open question (blocking the rename)

"jev-decision-layer" was not found in any local repo (trinity, t27, tri-net,
trios, website) or Railway service list. "wars" tab is not in the current
HUD list either (live site may run a newer branch). Need the exact location
(repo/service/branch) before renaming it to TRI.
