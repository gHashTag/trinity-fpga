//! Mint-on-acceptance authority — the reference oracle for the on-chain minters.
//!
//! WHAT THIS IS. A blockchain cannot run t27c, so the chain cannot itself check
//! that a spec was accepted. The only mint path is therefore a signed
//! ACCEPTANCE_ATTESTATION carried by an attestor quorum (see
//! specs/trinet/mint_on_acceptance.t27). This module is the golden model of the
//! rule the TON and Solana contracts must reproduce: it verifies M-of-N real
//! ed25519 signatures over the attestation digest, refuses a spent nonce
//! (no double-mint, including across chains), and refuses a mint that would
//! cross the 3^21 cap. Genesis minted supply is zero.
//!
//! It is tested here with real keys and real signatures so the security
//! properties are executed, not asserted in prose. The chain contracts are
//! checked against the same vectors; a divergence is a contract bug.
//!
//! 100% of TRI is mined this way and only this way — no pre-mine, no
//! allocation, no sale (owner decision 2026-09-24, settlement_law.t27).
//!
//! Author: Dmitrii Vasilev (@gHashTag)

const std = @import("std");
const Ed25519 = std.crypto.sign.Ed25519;
const Sha256 = std.crypto.hash.sha2.Sha256;

/// 3^21, the Trinity identity. Enforced on-chain as the mint ceiling.
pub const cap_tri: u64 = 10_460_353_203;

/// The signature is valid for exactly one chain, so a quorum for TON cannot be
/// replayed onto Solana. The nonce set is shared across chains regardless.
pub const Chain = enum(u8) { ton = 1, solana = 2 };

/// The message a quorum authorises. One valid attestation mints exactly once.
pub const Attestation = struct {
    /// Who did the work and receives the TRI (a 32-byte, chain-agnostic id).
    worker: [32]u8,
    /// hash(accepted spec/job + its receipt): ties the mint to specific work.
    work_id: [32]u8,
    chain: Chain,
    amount_mtri: u64,
    /// Unique across ALL chains; the minters share one spent set.
    global_nonce: u128,
    /// Rotation boundary for the attestor key set.
    epoch: u32,

    /// Canonical big-endian serialization, hashed to the digest the attestors
    /// sign. Every field is covered, so changing any of them invalidates the
    /// signatures.
    pub fn digest(self: Attestation) [32]u8 {
        var buf: [32 + 32 + 1 + 8 + 16 + 4]u8 = undefined;
        var i: usize = 0;
        @memcpy(buf[i..][0..32], &self.worker);
        i += 32;
        @memcpy(buf[i..][0..32], &self.work_id);
        i += 32;
        buf[i] = @intFromEnum(self.chain);
        i += 1;
        std.mem.writeInt(u64, buf[i..][0..8], self.amount_mtri, .big);
        i += 8;
        std.mem.writeInt(u128, buf[i..][0..16], self.global_nonce, .big);
        i += 16;
        std.mem.writeInt(u32, buf[i..][0..4], self.epoch, .big);
        var out: [32]u8 = undefined;
        Sha256.hash(&buf, &out, .{});
        return out;
    }
};

pub const Error = error{
    ZeroAmount,
    SubQuorum,
    WrongChain,
    WrongEpoch,
    ReplayedNonce,
    OverCap,
};

/// The mint authority. In production its state lives on-chain; here it is the
/// reference against which the TON and Solana implementations are checked.
pub const SpentSet = std.AutoHashMap(u128, void);

pub const Authority = struct {
    attestors: []const Ed25519.PublicKey,
    threshold: u8, // M of N
    chain: Chain,
    epoch: u32,
    minted_total: u64 = 0, // starts at zero: no pre-mine
    /// The spent-nonce ledger, shared by REFERENCE across every chain's
    /// authority: the TON and Solana minters must consult ONE set, or the same
    /// earning mints on both chains. The authority does not own it.
    spent: *SpentSet,

    pub fn init(
        attestors: []const Ed25519.PublicKey,
        threshold: u8,
        chain: Chain,
        epoch: u32,
        spent: *SpentSet,
    ) Authority {
        std.debug.assert(threshold >= 1);
        std.debug.assert(threshold <= attestors.len);
        return .{
            .attestors = attestors,
            .threshold = threshold,
            .chain = chain,
            .epoch = epoch,
            .spent = spent,
        };
    }

    /// Count DISTINCT attestors whose signature verifies over the digest. A
    /// contract cannot trust a claimed signer index, so we match each signature
    /// against every attestor key and de-duplicate — a repeated signature from
    /// one attestor cannot stuff the quorum, and a signature from a non-attestor
    /// key counts for nothing.
    fn quorumReached(self: Authority, dgst: [32]u8, sigs: []const [64]u8) bool {
        var seen = std.StaticBitSet(256).initEmpty();
        var distinct: usize = 0;
        for (sigs) |raw| {
            const sig = Ed25519.Signature.fromBytes(raw);
            for (self.attestors, 0..) |pk, idx| {
                if (idx >= 256) break;
                if (seen.isSet(idx)) continue;
                sig.verify(&dgst, pk) catch continue;
                seen.set(idx);
                distinct += 1;
                break;
            }
        }
        return distinct >= self.threshold;
    }

    /// The one mint path. On success the nonce is spent and the amount is added
    /// to the running total; returns the amount to mint. Any failure mints
    /// nothing and changes no state (the nonce is only spent after every check
    /// passes).
    pub fn authorizeMint(
        self: *Authority,
        att: Attestation,
        sigs: []const [64]u8,
    ) Error!u64 {
        if (att.amount_mtri == 0) return Error.ZeroAmount;
        if (att.chain != self.chain) return Error.WrongChain;
        if (att.epoch != self.epoch) return Error.WrongEpoch;
        if (self.spent.contains(att.global_nonce)) return Error.ReplayedNonce;
        if (!self.quorumReached(att.digest(), sigs)) return Error.SubQuorum;
        // Cap is checked last so an over-cap attempt cannot consume a nonce.
        const next = std.math.add(u64, self.minted_total, att.amount_mtri) catch
            return Error.OverCap;
        if (next > cap_tri) return Error.OverCap;

        self.spent.put(att.global_nonce, {}) catch return Error.OverCap;
        self.minted_total = next;
        return att.amount_mtri;
    }
};

// ---------------------------------------------------------------------------
// Tests — real ed25519 keys and signatures, every security property executed.
// ---------------------------------------------------------------------------

const testing = std.testing;

fn genKeys(n: usize, out_kp: []Ed25519.KeyPair, out_pk: []Ed25519.PublicKey) void {
    for (0..n) |i| {
        // Distinct deterministic seed per key: reproducible tests, no Io needed.
        var seed: [Ed25519.KeyPair.seed_length]u8 = [_]u8{0} ** Ed25519.KeyPair.seed_length;
        seed[0] = @intCast(i + 1);
        const kp = Ed25519.KeyPair.generateDeterministic(seed) catch unreachable;
        out_kp[i] = kp;
        out_pk[i] = kp.public_key;
    }
}

fn sign(kp: Ed25519.KeyPair, dgst: [32]u8) [64]u8 {
    const s = kp.sign(&dgst, null) catch unreachable;
    return s.toBytes();
}

fn sampleAtt(nonce: u128, amount: u64, chain: Chain) Attestation {
    return .{
        .worker = [_]u8{7} ** 32,
        .work_id = [_]u8{9} ** 32,
        .chain = chain,
        .amount_mtri = amount,
        .global_nonce = nonce,
        .epoch = 1,
    };
}

fn newSpent() SpentSet {
    return SpentSet.init(testing.allocator);
}

test "genesis minted supply is zero" {
    var kp: [3]Ed25519.KeyPair = undefined;
    var pk: [3]Ed25519.PublicKey = undefined;
    genKeys(3, &kp, &pk);
    var spent = newSpent();
    defer spent.deinit();
    const auth = Authority.init(&pk, 2, .ton, 1, &spent);
    try testing.expectEqual(@as(u64, 0), auth.minted_total);
}

test "a valid M-of-N quorum mints exactly the amount" {
    var kp: [3]Ed25519.KeyPair = undefined;
    var pk: [3]Ed25519.PublicKey = undefined;
    genKeys(3, &kp, &pk);
    var spent = newSpent();
    defer spent.deinit();
    var auth = Authority.init(&pk, 2, .ton, 1, &spent);

    const att = sampleAtt(1, 5, .ton);
    const d = att.digest();
    const sigs = [_][64]u8{ sign(kp[0], d), sign(kp[1], d) };

    try testing.expectEqual(@as(u64, 5), try auth.authorizeMint(att, &sigs));
    try testing.expectEqual(@as(u64, 5), auth.minted_total);
}

test "a sub-quorum mints nothing" {
    var kp: [3]Ed25519.KeyPair = undefined;
    var pk: [3]Ed25519.PublicKey = undefined;
    genKeys(3, &kp, &pk);
    var spent = newSpent();
    defer spent.deinit();
    var auth = Authority.init(&pk, 2, .ton, 1, &spent);

    const att = sampleAtt(1, 5, .ton);
    const sigs = [_][64]u8{sign(kp[0], att.digest())}; // 1 of 3, need 2
    try testing.expectError(Error.SubQuorum, auth.authorizeMint(att, &sigs));
    try testing.expectEqual(@as(u64, 0), auth.minted_total);
}

test "a repeated signature from one attestor cannot stuff the quorum" {
    var kp: [3]Ed25519.KeyPair = undefined;
    var pk: [3]Ed25519.PublicKey = undefined;
    genKeys(3, &kp, &pk);
    var spent = newSpent();
    defer spent.deinit();
    var auth = Authority.init(&pk, 2, .ton, 1, &spent);

    const att = sampleAtt(1, 5, .ton);
    const one = sign(kp[0], att.digest());
    const sigs = [_][64]u8{ one, one }; // same signer twice
    try testing.expectError(Error.SubQuorum, auth.authorizeMint(att, &sigs));
}

test "a non-attestor signature counts for nothing" {
    var kp: [4]Ed25519.KeyPair = undefined;
    var pk: [4]Ed25519.PublicKey = undefined;
    genKeys(4, &kp, &pk);
    var spent = newSpent();
    defer spent.deinit();
    // Only the first three are attestors; kp[3] is an outsider.
    var auth = Authority.init(pk[0..3], 2, .ton, 1, &spent);

    const att = sampleAtt(1, 5, .ton);
    const d = att.digest();
    const sigs = [_][64]u8{ sign(kp[0], d), sign(kp[3], d) }; // 1 real + 1 outsider
    try testing.expectError(Error.SubQuorum, auth.authorizeMint(att, &sigs));
}

test "a spent nonce is refused — no double-mint" {
    var kp: [3]Ed25519.KeyPair = undefined;
    var pk: [3]Ed25519.PublicKey = undefined;
    genKeys(3, &kp, &pk);
    var spent = newSpent();
    defer spent.deinit();
    var auth = Authority.init(&pk, 2, .ton, 1, &spent);

    const att = sampleAtt(1, 5, .ton);
    const d = att.digest();
    const sigs = [_][64]u8{ sign(kp[0], d), sign(kp[1], d) };

    _ = try auth.authorizeMint(att, &sigs);
    try testing.expectError(Error.ReplayedNonce, auth.authorizeMint(att, &sigs));
    try testing.expectEqual(@as(u64, 5), auth.minted_total); // still 5, not 10
}

test "the same global nonce cannot mint on a second chain" {
    var kp: [3]Ed25519.KeyPair = undefined;
    var pk: [3]Ed25519.PublicKey = undefined;
    genKeys(3, &kp, &pk);

    // ONE spent set, shared by both chains' authorities — the production invariant.
    var spent = newSpent();
    defer spent.deinit();
    var ton = Authority.init(&pk, 2, .ton, 1, &spent);
    var sol = Authority.init(&pk, 2, .solana, 1, &spent);

    const att_ton = sampleAtt(42, 5, .ton);
    const dt = att_ton.digest();
    _ = try ton.authorizeMint(att_ton, &[_][64]u8{ sign(kp[0], dt), sign(kp[1], dt) });

    // Same global_nonce, now aimed at Solana: refused by the shared set.
    const att_sol = sampleAtt(42, 5, .solana);
    const ds = att_sol.digest();
    try testing.expectError(
        Error.ReplayedNonce,
        sol.authorizeMint(att_sol, &[_][64]u8{ sign(kp[0], ds), sign(kp[1], ds) }),
    );
}

test "a TON quorum does not authorise a Solana mint (chain is signed)" {
    var kp: [3]Ed25519.KeyPair = undefined;
    var pk: [3]Ed25519.PublicKey = undefined;
    genKeys(3, &kp, &pk);
    var spent = newSpent();
    defer spent.deinit();
    var sol = Authority.init(&pk, 2, .solana, 1, &spent);

    // Signatures made over a TON attestation, submitted to the Solana authority.
    const att_ton = sampleAtt(1, 5, .ton);
    const d = att_ton.digest();
    const sigs = [_][64]u8{ sign(kp[0], d), sign(kp[1], d) };
    // The chain is in the digest, so these signatures are only valid for TON;
    // the Solana authority trips the chain guard first, mints nothing.
    try testing.expectError(Error.WrongChain, sol.authorizeMint(att_ton, &sigs));
}

test "a mint over the cap is refused and consumes no nonce" {
    var kp: [3]Ed25519.KeyPair = undefined;
    var pk: [3]Ed25519.PublicKey = undefined;
    genKeys(3, &kp, &pk);
    var spent = newSpent();
    defer spent.deinit();
    var auth = Authority.init(&pk, 2, .ton, 1, &spent);
    auth.minted_total = cap_tri - 3; // near the ceiling

    const att = sampleAtt(1, 5, .ton); // 5 would cross the cap
    const d = att.digest();
    const sigs = [_][64]u8{ sign(kp[0], d), sign(kp[1], d) };
    try testing.expectError(Error.OverCap, auth.authorizeMint(att, &sigs));
    try testing.expect(!auth.spent.contains(1)); // nonce not consumed
}

test "digest matches the cross-language golden vector" {
    // Independently computed with Python hashlib over the exact big-endian
    // layout (worker++work_id++chain++amount++nonce++epoch). The Solana and TON
    // contracts must reproduce THIS digest for the same attestation, or their
    // signatures verify against a different message than the attestors signed.
    const golden = [_]u8{
        0x9c, 0xe2, 0xce, 0xe5, 0x77, 0xfd, 0x87, 0xa7, 0x2b, 0x83, 0x7d, 0x56,
        0xc7, 0x28, 0xb7, 0x0a, 0x58, 0x0e, 0x36, 0x6f, 0x4a, 0x5b, 0x73, 0x39,
        0xdb, 0xa8, 0x14, 0x64, 0x39, 0xc1, 0xdd, 0xe7,
    };
    try testing.expectEqualSlices(u8, &golden, &sampleAtt(1, 5, .ton).digest());
}

test "a zero-amount attestation is refused" {
    var kp: [3]Ed25519.KeyPair = undefined;
    var pk: [3]Ed25519.PublicKey = undefined;
    genKeys(3, &kp, &pk);
    var spent = newSpent();
    defer spent.deinit();
    var auth = Authority.init(&pk, 2, .ton, 1, &spent);
    const att = sampleAtt(1, 0, .ton);
    const d = att.digest();
    const sigs = [_][64]u8{ sign(kp[0], d), sign(kp[1], d) };
    try testing.expectError(Error.ZeroAmount, auth.authorizeMint(att, &sigs));
}
