# TRI mint-on-acceptance contracts

Reference implementations of the on-chain minters that turn an accepted `.t27`
spec into mined `$TRI`. **100% of TRI is mined by accepted work — no pre-mine,
no allocation, no sale.**

## Status

| Artefact | What it is | Runs here? |
|---|---|---|
| `src/trinet/mint_authority.zig` | the **golden oracle**: the mint rule + M-of-N ed25519 quorum, tested | **yes — `zig test`, 13/13 pass** |
| `contracts/solana/tri_mint.rs` | Solana (Anchor) program mirroring the oracle | reference, unaudited, not built |
| `contracts/ton/tri_minter.fc` | TON (FunC) minter mirroring the oracle | reference, unaudited, not built |

The oracle is the source of truth for the *logic*: both contracts must
reproduce its behaviour, and its tests are the vectors to check them against. A
divergence is a bug in the contract, not in the oracle.

## What the oracle proves (executed, not asserted)

Run it:

```bash
zig test src/trinet/mint_authority.zig
```

- genesis minted supply is **zero**;
- a valid **M-of-N** quorum mints exactly the attested amount;
- a sub-quorum, a repeated signature from one attestor, and a non-attestor
  signature all mint **nothing**;
- a **spent nonce** is refused (no double-mint), **including across chains** via
  one shared ledger;
- **two chains together cannot cross the cap**: the minted total lives in the
  same shared ledger as the nonces, not one counter per chain;
- a TON quorum cannot authorise a Solana mint (the chain is inside the signed
  digest);
- a mint over the **3^21 cap** is refused and consumes no nonce;
- a zero-amount attestation is refused;
- the cap is 3^21 **whole** TRI, counted in the base unit (see below), and fits
  `u64`.

## One base unit: mTRI, decimals = 3

Every amount in the oracle, the relayer, and both contracts is **mTRI**, the
unit `src/trinet/ledger.zig` already settles in. On-chain it is the token's
smallest unit, so the TON jetton and the SPL mint both carry **decimals = 3**,
and the cap in base units is `CAP_MTRI = 3^21 × 1000 = 10_460_353_203_000`.

Until 2026-10-01 the cap was written in whole TRI (`CAP_TRI = 3^21`) but compared
against mTRI amounts, so the real ceiling was 1000× lower than 3^21 TRI. The
earlier docs said decimals = 18, which a `u64` SPL amount cannot hold for this
cap. Both are fixed here.

## One minter until the bridge exists

The supply rule is **sum across all chains ≤ cap**. The oracle enforces it with
one shared ledger. On-chain, a TON contract and a Solana program cannot read
each other's counters: each `minted_total` counts its own chain only, so two
live minters could together mint up to 2× the cap.

Therefore **exactly one minter may be deployed** until a bridge (or a single
chain of record with lock-and-mint on the other) is designed, specified and
tested. TON is the chain of record, so it goes first; the Solana program stays
a reference. This is the `CROSS_CHAIN_DOUBLE_MINT` open question in the spec.

## What is NOT here, and is not ours to do

Deployment, custody of the attestor keys, the choice of M and N, a security
audit, and the legal review of issuance and secondary trading. Those are the
owner's and counsel's actions. Nothing in this directory has been deployed, and
the two contract files must be audited before they are.

## Protocol of record

- `specs/trinet/mint_on_acceptance.t27` — the protocol and its honestly
  versioned trust model (V1 attestor quorum → V2 optimistic → V3 zk receipt).
- `docs/docs/depin/minting.md` — the human-readable design.
- `specs/trinet/settlement_law.t27` — what earns a TRI in the first place.
