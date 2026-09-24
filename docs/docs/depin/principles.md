---
sidebar_label: 'Principles'
title: 'What TRI is, and what pays it'
description: 'The one principle behind $TRI, and how the earlier contradictions were resolved'
---

# What TRI is, and what pays it

Owner decision, 2026-09-24. This page is the plain-language principle; the
source of truth is the spec `specs/trinet/settlement_law.t27`.

## The principle, in one line

**TRI is real, transferable money, and 100% of it is mined by accepted work --
there is no pre-mine and no sale.** Every accepted turn -- a spec completed, a
function repaired until `t27c` accepts it, a job computed correctly on a board --
mints TRI to whoever did it. The minted supply at genesis is zero; every token up
to the 3^21 cap is panned, not printed. TRI has value because the only way to
hold one is to have done work a verifier accepted, backed by a receipt anyone can
recompute.

## What this replaces

Two documents used to disagree, and that was the whole contradiction:

| Where | Used to say | Now |
|---|---|---|
| the Queen game hero | an accepted turn is a **non-transferable integer**; the counters are real, the wallet is not | the counter **is** the wallet: XP is a view of the TRI you have earned |
| `settlement_law.t27` | TRI is a **non-transferable internal work credit**; nothing mints a chain asset | TRI is a **transferable token**, issued on-chain |
| the DePIN tokenomics | a full `$TRI` token on Ethereum Sepolia | the same token, chains of record **TON** and **Solana** |

There is now one answer: TRI is money.

## The parts that did not change

The engineering that makes TRI worth paying is untouched, and it is the reason
the token is honest rather than speculative:

- **Cheating is unprofitable by construction.** `p·s > r` -- audit rate times
  slash exceeds the reward -- is checked before the ledger will start.
- **A receipt is the proof of pay.** The compiler's verdict, and on hardware
  the board's signed result, back every TRI. This session a board settled
  96 of 96 jobs with receipts on real silicon.
- **Damage is not dishonesty.** An honest board on a bad cable is not slashed.

TRI is a *payment* token: it is only ever earned for verified work, never sold
as a promise. That is what keeps it out of the failure it would otherwise walk
into.

## Chains of record

- **TON** -- because the users and the distribution are in Telegram: Mini Apps,
  TON Connect, `@wallet`. TON Foundation funds exactly this kind of project.
- **Solana** -- the original plan, and where deep DEX liquidity lives.
- One canonical supply of **3^21 = 10,460,353,203 TRI** (the 21-trit Trinity
  identity), mirrored across both chains by a lock-and-mint bridge, so the two
  are one token, not two.
- The Ethereum Sepolia contract was the testnet proof of concept and is
  superseded as a chain of record.

## What the override still owes (open)

Making TRI real money answers a question the credit scoping had deliberately
avoided, so the answer now has to be built, not assumed:

1. **A compliant issuance path** -- a foundation entity in a VASP jurisdiction
   (Switzerland, Singapore, UAE, Cayman/BVI), reviewed by crypto counsel. The
   cautionary precedent is *SEC v. Telegram*: a single company selling its own
   token to fund itself was the whole defect, and TRI must be distributed as
   payment for work rather than sold that way.
2. **The bridge** -- one canonical supply across TON and Solana needs a
   lock-and-mint bridge, which is the one real added moving part of going
   multi-chain.
3. **XP = TRI wiring** -- the leaderboard and the ledger must show the same
   number, so a rank is a balance.

No counsel has reviewed any of this yet. That review is the first task this
decision creates, and it is recorded as `[compliance path OPEN]` in the spec.
