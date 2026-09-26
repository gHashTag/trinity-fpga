# TRI mint-on-acceptance contracts

Reference implementations of the on-chain minters that turn an accepted `.t27`
spec into mined `$TRI`. **100% of TRI is mined by accepted work — no pre-mine,
no allocation, no sale.**

## Status

| Artefact | What it is | Runs here? |
|---|---|---|
| `src/trinet/mint_authority.zig` | the **golden oracle**: the mint rule + M-of-N ed25519 quorum, tested | **yes — `zig test`, 10/10 pass** |
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
  one shared nonce set;
- a TON quorum cannot authorise a Solana mint (the chain is inside the signed
  digest);
- a mint over the **3^21 cap** is refused and consumes no nonce;
- a zero-amount attestation is refused.

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
