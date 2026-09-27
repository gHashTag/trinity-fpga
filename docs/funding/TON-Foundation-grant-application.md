# TON Foundation grant application — TRI CLAW / t27.ai

Draft, 2026-09-24. Not submitted. Maintainer: Dmitrii Vasilev (@gHashTag).

## One sentence

t27.ai is a Telegram-native network where agents and people earn a token by
producing work a compiler can verify, and TRI CLAW is the open FPGA node that
runs those agents on-device — we are asking TON to fund the on-chain minting and
the Telegram Mini App that make an accepted `.t27` spec pay real, mined TRI.

## Which TON priority this fits

Two of the five Champion Grant verticals, directly:

- **In-app economy of Telegram.** t27.ai already runs as a web app; the ask
  includes turning it into a Mini App with TON Connect and `@wallet`, so earning
  and holding TRI happens inside Telegram.
- **AI (agents, interfaces, infrastructure).** The network's workers are small
  ternary code models (IGLA) whose output is judged by a compiler, not by a
  vote. That is verifiable AI work, which is the honest form of an on-chain AI
  economy.

We would also welcome the non-commercial / public-goods track: the compiler,
the specs and the FPGA toolchain are open.

## What already exists (verifiable, not promised)

Everything below is in public repositories and can be checked, not taken on
trust. That discipline is the point of the project.

| Claim | Evidence |
|---|---|
| A ternary compute node runs on real silicon and settles work with receipts | 96 of 96 jobs accepted on an ALINX AX7203 (XC7A200T), 2026-09-24 |
| The token mints only for accepted work, 100% mined, zero pre-mine | `specs/trinet/mint_on_acceptance.t27`; mint rule tested 14/14 (`zig test`) |
| The mint rule is honest about its trust model | attestor-quorum V1 labelled "not trustless"; V2/V3 designed, not overclaimed |
| The Solana minter matches the rule across languages | `cargo test` 4/4; one digest vector identical in Zig, Python and Rust |
| Small models do verifiable code work | IGLA pilot: ternary vs full-precision ladder, measured bits/byte, t27 benchmark judged by `t27c` |

## What the grant would fund

Concrete, milestone-gated, all of it buildable now:

1. **On-chain mint on TON.** A jetton minter whose only mint path is a valid
   acceptance attestation (reference already written, `contracts/ton/`), plus
   the relayer that carries a settled earning to it (reference written,
   `src/trinet/relayer.zig`). Milestone: a testnet mint driven by a real
   accepted spec.
2. **The Telegram Mini App.** t27.ai's Queen board as a Mini App with TON
   Connect: a worker signs in with their Telegram wallet and their accepted work
   mints TRI to it. Milestone: an end-to-end earn on testnet inside Telegram.
3. **A security audit** of the two minters and the bridge, before any mainnet
   deploy.

## What we are NOT claiming

- Nothing is deployed on any live network today; no contract, key or mint exists.
- V1 trusts an honest majority of an attestor set; who holds those keys is an
  open governance question, not a solved one.
- The IGLA models are small and early; they do not yet write specs unaided.
- The token funds no development directly (it is mined, not sold); this grant and
  hardware sales are the funding, and that is by design.

## Ask

A Champion or public-goods grant covering milestones 1–3. We can start milestone
1 immediately: the mint rule, the relayer and the reference contracts are built
and tested; what remains is the on-chain deployment path and the audit, which are
exactly what a grant de-risks.

## Links

- Protocol: `specs/trinet/mint_on_acceptance.t27`, `docs/docs/depin/minting.md`
- Principle: `docs/docs/depin/principles.md` (100% mined, zero pre-mine)
- Node on silicon: `specs/trinet/ternary_hw_verification.t27`
- Repositories: gHashTag/trinity-fpga, gHashTag/t27, gHashTag/trinity
