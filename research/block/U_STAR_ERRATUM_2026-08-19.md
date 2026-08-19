# Erratum: the five-family u* wording (2026-08-19, same-day self-audit)

The five-family table stands as measured (13pt [0,0.55] grid, G1-gated fp32
baselines): gpt2 0.25, opt 0.25, qwen 0.30, smollm2 0.35, pythia 0.40. Three
wording corrections from an adversarial audit of commit 6fa214e02's message,
each verified against the stored artifacts:

1. **"no shared value across architectures" is false by the same sentence's own
   numbers** — gpt2 and opt report the identical u* = 0.25. The defensible
   statement, and the one the negative result actually needs, is narrower: at
   least one between-family separation survives fold resampling — gpt2/opt
   (0.25) vs pythia (0.35–0.40): gap 0.1333 vs within-model fold spread 0.0500
   (u_eval_floor.json). One surviving separation is sufficient for "no single
   constant transfers"; five distinct values was never needed and is not what
   the data shows.

2. **qwen and smollm2 are single-fold measurements.** Their u* margins over the
   0.05-neighbours (qwen: 0.0228 over u=0.20; smollm2: 0.0434 over u=0.30) are
   below their own stored tie-rule floors, so their optima are stated at grid
   resolution only. Neither was fold-resampled; fold coverage is 2 of 5
   families (gpt2, pythia).

3. **opt's minimum is a plateau, not a point**: {0.15, 0.20, 0.25} all lie
   within opt's tie floor (0.0667) of its minimum (Δ to 0.20 is 0.0087, 7.7x
   below the floor). A sharp minimum is established for exactly one family,
   gpt2 (walls ~0.51/0.58 ppl vs a 0.0003 floor, argmin stable across all
   three folds).

The practical conclusion is unchanged and, if anything, sharpened: u* must be
measured per family (cost of the wrong point: +0.56 to +3.47 ppl at identical
bits), and no universal alignment constant exists to transfer — carried by the
fold-validated gpt2/opt-vs-pythia separation, not by the raw enumeration.
