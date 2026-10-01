# TRI mint-on-acceptance contracts

Reference implementations of the on-chain minters that turn an accepted `.t27`
spec into mined `$TRI`. **100% of TRI is mined by accepted work — no pre-mine,
no allocation, no sale.**

## Status

| Artefact | What it is | Runs here? |
|---|---|---|
| `src/trinet/mint_authority.zig` | the **golden oracle**: the mint rule + M-of-N ed25519 quorum, tested | **yes — `zig test`, 15/15 pass** |
| `contracts/solana/tri_mint.rs` | Solana (Anchor) program mirroring the oracle | reference, unaudited, not built |
| `contracts/ton/tri_minter.fc` | TON (FunC) jetton master mirroring the oracle | **built and executed in a TON VM sandbox — `npm test`, 27/27 pass**; unaudited, not deployed |

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

## The TON minter, executed (not asserted)

```bash
cd contracts/ton && npm ci && npm test     # 27 tests, TON VM via @ton/sandbox
npm run build                              # build/*.boc + code hashes
```

The minter **is** the TEP-74 jetton master. It has **no admin**:
`get_jetton_data` reports `addr_none`, and the only path that raises the supply
is `op::mint_on_att` (`"TRI1"`) carrying a valid M-of-N quorum. The wallet is the
TON Foundation reference wallet, vendored unchanged at a pinned commit
(`vendor/token-contract/UPSTREAM_COMMIT`).

The tests replay the oracle, byte for byte: the same key seeds, the same
93-byte digest (golden `9ce2cee5…dde7`), and **the oracle's own signature
bytes** (pinned in `mint_authority.zig`) mint 5 mTRI in the VM. Every oracle
refusal has its VM twin with the contract's exit code: sub-quorum (105), one
attestor counted twice (105), an outsider (105), replay (104), wrong chain
(102), wrong epoch (103), zero amount (101), over the cap without spending the
nonce (106). On top, what only a chain has: a burn lowers circulation but never
reopens the cap counter, a forged `burn_notification` is refused (109), the
reference admin ops `mint`/`change_admin`/`change_content` do not exist
(0xffff), and minted TRI moves through an ordinary TEP-74 transfer.

| Code | Hash (func-js 0.11, pinned in `package-lock.json`) |
|---|---|
| `tri_minter.fc` | `88475d44991be38806dd1511125f101f0c5c71bf827470e508838a07d57579e5` |
| reference jetton wallet | `a760d629d5343e76d045017d9dc216fc8a307a8377815feb2b0a5c490e733486` |

### Rotation

`op::rotate` (`"TRIR"`) lets the **current** quorum hand the mint to a new
attestor set at `epoch + 1`, signed over a digest that includes the minter's
own address (`rotationDigest` in the oracle, golden `49f46c26…ca77`). After a
rotation the old set's attestations fail on the epoch, and the old set's
signatures cannot pass as the new set's. This mechanism is **a proposal**: the
spec lists key rotation among the owner's governance questions, and nothing
here answers that question for them.

### Testnet deploy

`scripts/deploy-testnet.ts` holds no key and sends nothing. It prints the
minter's testnet address and a `ton://transfer` link carrying its state init,
for the operator to pay from a testnet wallet. There is no mainnet flag.

`scripts/testnet.ts` is the testnet operator: `wallet` creates or shows a v5r1
deployer, `attestors` a 2-of-3 testnet attestor set, then `deploy`, `mint`,
`status`. Keys live in `~/.tri-testnet` (mode 0600), never in the repository.
The endpoint is testnet's and there is no network flag. While one operator
holds all three attestor keys, the testnet quorum is one party with three keys:
a pipeline test, not a trust model.

### Known limits (read before any deploy)

- **No deployment domain in the mint digest.** The 93-byte attestation does not
  name the minter, so an attestation is valid on **every** minter that trusts
  the same keys and epoch. A testnet deploy MUST use testnet-only attestor
  keys. The proper fix (the minter address inside the digest) changes the
  oracle, the relayer, both contracts and the Python attestor together, so it
  is its own change. Rotation already carries the address.
- **The spent-nonce dictionary only grows.** Its storage rent is paid from the
  minter's balance, which must be topped up for the life of the contract.
- **A bounced mint is lost to the worker.** If the wallet deploy bounces, the
  supply is rolled back but the nonce stays spent (a re-mint would need a new
  nonce). The 0.05 TON value floor makes a bounce unlikely, not impossible.

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
the two contract files must be audited before they are. A sandbox pass is
evidence the contract matches the oracle; it is not an audit.

## Protocol of record

- `specs/trinet/mint_on_acceptance.t27` — the protocol and its honestly
  versioned trust model (V1 attestor quorum → V2 optimistic → V3 zk receipt).
- `docs/docs/depin/minting.md` — the human-readable design.
- `specs/trinet/settlement_law.t27` — what earns a TRI in the first place.
