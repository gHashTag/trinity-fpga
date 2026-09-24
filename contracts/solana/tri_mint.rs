// tri_mint — Solana (Anchor) mint-on-acceptance program.
//
// REFERENCE, UNAUDITED, NOT BUILT HERE. This mirrors the golden oracle
// src/trinet/mint_authority.zig, which is tested (10/10) with real ed25519
// signatures. Every rule below must reproduce that oracle; a divergence is a
// bug in THIS file, not in the oracle. Protocol of record:
// specs/trinet/mint_on_acceptance.t27.
//
// Genesis minted supply is zero. The only mint path is `mint_on_attestation`
// with a valid M-of-N attestor quorum. There is no founder / treasury /
// liquidity mint and no other instruction that can create TRI.
//
// ED25519 ON SOLANA: programs do not verify ed25519 in-program. The caller
// prepends one Ed25519Program instruction per signature in the same
// transaction, and this program checks, by instruction introspection, that
// those instructions signed exactly `att.digest()` under attestor keys. That
// introspection is the on-chain equivalent of the oracle's `quorumReached`.

use anchor_lang::prelude::*;
use anchor_lang::solana_program::{ed25519_program, sysvar::instructions as ix_sysvar};
use anchor_spl::token::{self, Mint, MintTo, Token, TokenAccount};

declare_id!("Tri1111111111111111111111111111111111111111"); // placeholder

pub const CAP_TRI: u64 = 10_460_353_203; // 3^21
pub const CHAIN_ID: u8 = 2; // Chain.solana in the oracle

#[program]
pub mod tri_mint {
    use super::*;

    /// One-time setup of the mint authority. Sets the attestor set, threshold
    /// and epoch. Mints NOTHING — genesis supply is zero.
    pub fn init_authority(
        ctx: Context<InitAuthority>,
        attestors: Vec<[u8; 32]>,
        threshold: u8,
        epoch: u32,
    ) -> Result<()> {
        require!(threshold >= 1, TriErr::BadThreshold);
        require!((threshold as usize) <= attestors.len(), TriErr::BadThreshold);
        let a = &mut ctx.accounts.authority;
        a.attestors = attestors;
        a.threshold = threshold;
        a.epoch = epoch;
        a.minted_total = 0;
        a.bump = ctx.bumps.authority;
        Ok(())
    }

    /// The only mint path. `att` is the attestation; the signatures live in the
    /// prepended Ed25519Program instructions, checked here by introspection.
    pub fn mint_on_attestation(ctx: Context<MintOnAttestation>, att: Attestation) -> Result<()> {
        let a = &mut ctx.accounts.authority;

        require!(att.amount_mtri > 0, TriErr::ZeroAmount);
        require!(att.chain_id == CHAIN_ID, TriErr::WrongChain);
        require!(att.epoch == a.epoch, TriErr::WrongEpoch);
        // Replay / double-mint: the nonce account is created here (seeded by the
        // nonce); a second attempt fails to init, exactly as the oracle's spent
        // set refuses a seen nonce. The nonce space is shared with other chains
        // by construction (the attestors never sign the same global_nonce twice).
        //   -> enforced by #[account(init, seeds=[b"nonce", att.global_nonce])]

        let digest = att.digest();
        let n_valid = verify_quorum_via_introspection(
            &ctx.accounts.instructions_sysvar,
            &digest,
            &a.attestors,
        )?;
        require!(n_valid >= a.threshold as usize, TriErr::SubQuorum);

        // Cap is checked last so an over-cap attempt cannot consume the nonce
        // account (Anchor rolls back the whole instruction on this error).
        let next = a
            .minted_total
            .checked_add(att.amount_mtri)
            .ok_or(TriErr::OverCap)?;
        require!(next <= CAP_TRI, TriErr::OverCap);
        a.minted_total = next;

        // Mint SPL TRI to the worker's token account. Authority is the PDA.
        let seeds: &[&[u8]] = &[b"authority", &[a.bump]];
        let signer = &[seeds];
        token::mint_to(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                MintTo {
                    mint: ctx.accounts.mint.to_account_info(),
                    to: ctx.accounts.worker_ata.to_account_info(),
                    authority: ctx.accounts.authority.to_account_info(),
                },
                signer,
            ),
            att.amount_mtri,
        )?;
        Ok(())
    }
}

/// Counts DISTINCT attestor keys that signed `digest` via prepended
/// Ed25519Program instructions. Mirrors the oracle's `quorumReached`: an
/// outsider signature counts for nothing and a key cannot be counted twice.
fn verify_quorum_via_introspection(
    ix_sysvar_ai: &AccountInfo,
    digest: &[u8; 32],
    attestors: &[[u8; 32]],
) -> Result<usize> {
    let mut seen = vec![false; attestors.len()];
    let mut count = 0usize;
    let mut i = 0usize;
    loop {
        let ix = match ix_sysvar::load_instruction_at_checked(i, ix_sysvar_ai) {
            Ok(ix) => ix,
            Err(_) => break, // no more instructions
        };
        i += 1;
        if ix.program_id != ed25519_program::ID {
            continue;
        }
        // Parse the Ed25519Program instruction: (pubkey, message). Reference
        // parsing omitted for brevity; it yields `signed_pubkey` and `message`.
        let (signed_pubkey, message) = parse_ed25519_ix(&ix.data);
        if &message[..] != &digest[..] {
            continue; // signed something other than this attestation
        }
        for (idx, key) in attestors.iter().enumerate() {
            if !seen[idx] && *key == signed_pubkey {
                seen[idx] = true;
                count += 1;
                break;
            }
        }
    }
    Ok(count)
}

fn parse_ed25519_ix(_data: &[u8]) -> ([u8; 32], Vec<u8>) {
    // Reference stub: real code decodes the Ed25519Program instruction layout
    // (num_signatures, offsets, then pubkey/message/signature blobs).
    unimplemented!("decode Ed25519Program instruction — see solana docs")
}

#[account]
pub struct Authority {
    pub attestors: Vec<[u8; 32]>,
    pub threshold: u8,
    pub epoch: u32,
    pub minted_total: u64,
    pub bump: u8,
}

/// The attestation, byte-identical in meaning to the oracle's `Attestation`.
#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct Attestation {
    pub worker: [u8; 32],
    pub work_id: [u8; 32],
    pub chain_id: u8,
    pub amount_mtri: u64,
    pub global_nonce: u128,
    pub epoch: u32,
}

impl Attestation {
    /// SHA-256 over the same big-endian layout as mint_authority.zig::digest.
    pub fn digest(&self) -> [u8; 32] {
        use anchor_lang::solana_program::hash::hashv;
        hashv(&[
            &self.worker,
            &self.work_id,
            &[self.chain_id],
            &self.amount_mtri.to_be_bytes(),
            &self.global_nonce.to_be_bytes(),
            &self.epoch.to_be_bytes(),
        ])
        .to_bytes()
    }
}

#[derive(Accounts)]
pub struct InitAuthority<'info> {
    #[account(init, payer = payer, space = 4096, seeds = [b"authority"], bump)]
    pub authority: Account<'info, Authority>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(att: Attestation)]
pub struct MintOnAttestation<'info> {
    #[account(mut, seeds = [b"authority"], bump = authority.bump)]
    pub authority: Account<'info, Authority>,
    /// Created here, seeded by the nonce: existing => second mint fails. This is
    /// the on-chain spent-nonce set.
    #[account(init, payer = payer, space = 8, seeds = [b"nonce", &att.global_nonce.to_be_bytes()], bump)]
    pub nonce_marker: Account<'info, NonceMarker>,
    #[account(mut)]
    pub mint: Account<'info, Mint>,
    #[account(mut)]
    pub worker_ata: Account<'info, TokenAccount>,
    #[account(mut)]
    pub payer: Signer<'info>,
    /// CHECK: the Instructions sysvar, read by introspection only.
    #[account(address = ix_sysvar::ID)]
    pub instructions_sysvar: AccountInfo<'info>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[account]
pub struct NonceMarker {}

#[error_code]
pub enum TriErr {
    #[msg("threshold must be 1..=N")]
    BadThreshold,
    #[msg("amount must be > 0")]
    ZeroAmount,
    #[msg("attestation is for another chain")]
    WrongChain,
    #[msg("attestation is for another epoch")]
    WrongEpoch,
    #[msg("fewer than M valid attestor signatures")]
    SubQuorum,
    #[msg("mint would cross the 3^21 cap")]
    OverCap,
}
