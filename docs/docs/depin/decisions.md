---
sidebar_label: 'Open decisions'
title: 'TRI: what is decided, and what only the owner can decide'
description: 'The decision record between the mint design and a real jetton on TON'
---

# TRI: what is decided, and what only the owner can decide

:::caution NOTHING IS DEPLOYED
This page records the state as of 2026-10-01. No contract, key or mint exists.
Every item marked **PROPOSED** is a recommendation awaiting the owner, not a
decision.
:::

The goal this page serves: a person who writes a `.t27` spec that is accepted
mines TRI, and can later move it to a wallet and trade it on a DEX as a TON
jetton. Between today and that goal sit the items below.

## Decided (in code, tested)

| # | Decision | Where |
|---|---|---|
| D1 | 100% of TRI is mined by accepted work; genesis supply 0; no allocation, no sale. | `specs/trinet/mint_on_acceptance.t27` |
| D2 | Cap is 3^21 whole TRI. | same |
| D3 | **One base unit: mTRI, decimals = 3.** `CAP_MTRI = 10_460_353_203_000`. Fixes the cap that was compared in mTRI while written in TRI (1000x too low) and the decimals = 18 that a `u64` SPL amount cannot hold. | `src/trinet/mint_authority.zig`, both contracts |
| D4 | **One shared ledger** (spent nonces AND minted total) across chains. Fixes the per-chain total that let TON + Solana mint 2x the cap. | `mint_authority.zig` test "two chains together cannot cross the cap" |
| D5 | **One minter until the bridge exists.** TON (chain of record) first; Solana stays a reference. | `contracts/README.md` |

## Open: only the owner can decide

| # | Question | PROPOSED | Why it blocks |
|---|---|---|---|
| O1 | Is mined TRI transferable outside the game? The territory economy walls proof units off from money. | Lift the wall **for spec authorship only**; compute proof units stay walled. | Without it, "sell on a DEX" contradicts the game's own rules. |
| O2 | How much TRI does one accepted spec mint? | A fixed amount per accepted spec in epoch 1, published before the first mint, never retroactive. | The earnings ledger can count specs today; it cannot show a TRI number until this exists. |
| O3 | M and N of the attestor quorum, who holds the keys, how a key is rotated. | Not proposed: a governance choice (`KEY_CUSTODY_AND_ATTESTOR_SET`). | V1 is exactly as honest as this set. |
| O4 | What "accepted" means for minting. Today an accept needs criteria, a commit and a reviewer but **no merge and no CI**, and CI can later take an accept back. | Mint only for accepts whose commit is merged to the default branch and not revoked; until then earnings are recorded, not mintable. | Minting on a revocable verdict mints tokens that cannot be clawed back. |
| O5 | Legal entity, issuance and secondary-trading review. | Counsel. | Not an engineering question; nothing deploys before it. |
| O6 | Liquidity: who seeds the first pool, with what. | Owner. A pool is outside this protocol: D1 forbids a treasury mint for it. | Without a pool there is no price, and "sell" means OTC. |

## The path, in order

1. **Earnings ledger, no token.** Every accepted `.t27` turn is recorded,
   append-only, with the commit it was judged on; revocations are recorded too.
   Public, labelled "mined, not withdrawable".
2. O1, O2, O4 answered → the ledger shows TRI amounts.
3. O3, O5 answered → audit of `contracts/ton/tri_minter.fc` → testnet jetton →
   mainnet jetton. Withdrawal = the attestors sign the recorded earnings.
4. O6 → a pool exists; the author can sell.
