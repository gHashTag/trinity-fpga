//! Host-testable core of the Solana mint-on-acceptance program.
//!
//! Mirrors the golden oracle src/trinet/mint_authority.zig and the deployable
//! program ../tri_mint.rs. Verified with `cargo test` without a validator:
//! the attestation digest must equal the cross-language golden vector, and the
//! Ed25519Program-instruction parser + quorum count must behave like the oracle.

use sha2::{Digest, Sha256};

pub const CHAIN_TON: u8 = 1;
pub const CHAIN_SOLANA: u8 = 2;
pub const CAP_TRI: u64 = 10_460_353_203; // 3^21

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
        let mut h = Sha256::new();
        h.update(self.worker);
        h.update(self.work_id);
        h.update([self.chain_id]);
        h.update(self.amount_mtri.to_be_bytes());
        h.update(self.global_nonce.to_be_bytes());
        h.update(self.epoch.to_be_bytes());
        h.finalize().into()
    }
}

/// Ed25519Program instruction data layout (Solana):
///   count:u8, pad:u8, then `count` * Offsets(7 * u16 LE = 14 bytes),
///   then the referenced pubkey/signature/message bytes appended.
/// Returns (pubkey, message) for every offsets entry that references THIS
/// instruction's own data (instruction_index == u16::MAX). The runtime has
/// already verified the signature, so the program only matches (pubkey, msg).
pub fn parse_ed25519_ix(data: &[u8]) -> Vec<([u8; 32], Vec<u8>)> {
    let mut out = Vec::new();
    if data.len() < 2 {
        return out;
    }
    let count = data[0] as usize;
    let rd = |p: usize| -> usize { u16::from_le_bytes([data[p], data[p + 1]]) as usize };
    const SELF: usize = u16::MAX as usize;
    let mut off = 2usize;
    for _ in 0..count {
        if off + 14 > data.len() {
            break;
        }
        let sig_ix = rd(off + 2);
        let pk_off = rd(off + 4);
        let pk_ix = rd(off + 6);
        let msg_off = rd(off + 8);
        let msg_sz = rd(off + 10);
        let msg_ix = rd(off + 12);
        off += 14;
        if pk_ix != SELF || msg_ix != SELF || sig_ix != SELF {
            continue; // references another instruction; out of scope for this parser
        }
        if pk_off + 32 > data.len() || msg_off + msg_sz > data.len() {
            continue;
        }
        let mut pk = [0u8; 32];
        pk.copy_from_slice(&data[pk_off..pk_off + 32]);
        out.push((pk, data[msg_off..msg_off + msg_sz].to_vec()));
    }
    out
}

/// Count DISTINCT attestors that signed `digest`, across all Ed25519Program
/// instruction blobs. An outsider key counts for nothing; one key counts once.
pub fn count_quorum(digest: &[u8; 32], attestors: &[[u8; 32]], ed25519_ixs: &[&[u8]]) -> usize {
    let mut seen = vec![false; attestors.len()];
    let mut n = 0usize;
    for ix in ed25519_ixs {
        for (pk, msg) in parse_ed25519_ix(ix) {
            if msg.as_slice() != digest {
                continue;
            }
            for (i, a) in attestors.iter().enumerate() {
                if !seen[i] && *a == pk {
                    seen[i] = true;
                    n += 1;
                    break;
                }
            }
        }
    }
    n
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::{Signer, SigningKey};

    fn sample() -> Attestation {
        Attestation {
            worker: [7u8; 32],
            work_id: [9u8; 32],
            chain_id: CHAIN_TON,
            amount_mtri: 5,
            global_nonce: 1,
            epoch: 1,
        }
    }

    fn key(seed: u8) -> SigningKey {
        let mut s = [0u8; 32];
        s[0] = seed;
        SigningKey::from_bytes(&s)
    }

    /// Build a single-signature Ed25519Program instruction, the layout Solana's
    /// own builder produces, so the parser is tested against the real format.
    fn build_ed25519_ix(pubkey: &[u8; 32], sig: &[u8; 64], msg: &[u8]) -> Vec<u8> {
        let header = 2 + 14; // count + pad + one offsets struct
        let pk_off = header;
        let sig_off = pk_off + 32;
        let msg_off = sig_off + 64;
        let selfidx = u16::MAX.to_le_bytes();
        let mut d = Vec::new();
        d.push(1u8); // count
        d.push(0u8); // pad
        d.extend_from_slice(&(sig_off as u16).to_le_bytes());
        d.extend_from_slice(&selfidx);
        d.extend_from_slice(&(pk_off as u16).to_le_bytes());
        d.extend_from_slice(&selfidx);
        d.extend_from_slice(&(msg_off as u16).to_le_bytes());
        d.extend_from_slice(&(msg.len() as u16).to_le_bytes());
        d.extend_from_slice(&selfidx);
        d.extend_from_slice(pubkey);
        d.extend_from_slice(sig);
        d.extend_from_slice(msg);
        d
    }

    #[test]
    fn digest_matches_cross_language_golden() {
        // Same vector asserted in mint_authority.zig and computed in Python.
        let g = hex::decode("9ce2cee577fd87a72b837d56c728b70a580e366f4a5b7339dba8146439c1dde7")
            .unwrap();
        assert_eq!(sample().digest().to_vec(), g);
    }

    #[test]
    fn parser_extracts_pubkey_and_message() {
        let sk = key(1);
        let pk = sk.verifying_key().to_bytes();
        let d = sample().digest();
        let sig = sk.sign(&d).to_bytes();
        let ix = build_ed25519_ix(&pk, &sig, &d);
        let pairs = parse_ed25519_ix(&ix);
        assert_eq!(pairs.len(), 1);
        assert_eq!(pairs[0].0, pk);
        assert_eq!(pairs[0].1, d.to_vec());
    }

    #[test]
    fn quorum_counts_distinct_and_ignores_outsider_and_duplicate() {
        let a0 = key(1);
        let a1 = key(2);
        let a2 = key(3);
        let outsider = key(9);
        let attestors = [
            a0.verifying_key().to_bytes(),
            a1.verifying_key().to_bytes(),
            a2.verifying_key().to_bytes(),
        ];
        let d = sample().digest();
        let mk = |sk: &SigningKey| build_ed25519_ix(&sk.verifying_key().to_bytes(), &sk.sign(&d).to_bytes(), &d);
        let i0 = mk(&a0);
        let i1 = mk(&a1);
        let io = mk(&outsider);

        // two real attestors + one outsider -> quorum 2 (outsider ignored)
        assert_eq!(count_quorum(&d, &attestors, &[&i0, &i1, &io]), 2);
        // the same real attestor twice -> counted once (no quorum stuffing)
        assert_eq!(count_quorum(&d, &attestors, &[&i0, &i0]), 1);
    }

    #[test]
    fn a_signature_over_a_different_message_does_not_count() {
        let a0 = key(1);
        let attestors = [a0.verifying_key().to_bytes()];
        let d = sample().digest();
        // sign a DIFFERENT message, then present it against digest d
        let other = [0xABu8; 32];
        let ix = build_ed25519_ix(&a0.verifying_key().to_bytes(), &a0.sign(&other).to_bytes(), &other);
        assert_eq!(count_quorum(&d, &attestors, &[&ix]), 0);
    }
}
