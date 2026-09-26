//! Relayer — turns a settled ledger earning into an on-chain mint authorisation.
//!
//! It holds NO mint power. Its only job is to carry a message the attestors
//! signed: watch the ledger (src/trinet/ledger.zig) for a settled earning,
//! build the ACCEPTANCE_ATTESTATION (specs/trinet/mint_on_acceptance.t27),
//! gather M-of-N attestor signatures, and hand the bundle to the chain the
//! worker chose. The chain's minter is the tested authority in
//! src/trinet/mint_authority.zig; this module closes the loop up to that call.
//!
//! What is modelled here (and tested): the earning -> attestation mapping, the
//! work_id binding, and that the produced bundle is accepted by the mint
//! authority. What is NOT here: live RPC submission and remote attestor custody,
//! which are gated on deployment and keys.
//!
//! Author: Dmitrii Vasilev (@gHashTag)

const std = @import("std");
const Ed25519 = std.crypto.sign.Ed25519;
const Sha256 = std.crypto.hash.sha2.Sha256;
const mint = @import("mint_authority.zig");

/// A settled earning, as the ledger records it (src/trinet/ledger.zig:settle
/// credits `node_id` for an accepted job). The relayer maps the ledger's u32
/// node identity to the 32-byte on-chain worker address the operator registered.
pub const SettledEarning = struct {
    node_id: u32,
    worker_address: [32]u8,
    amount_mtri: u64,
    /// From the receipt (protocol.zig): binds the earning to the exact job.
    job_nonce: [4]u8,
    receipt_tag: u64,
};

/// work_id = hash(node_id ++ job_nonce ++ receipt_tag): ties a mint to specific
/// verified work, so the same amount for two different jobs is two attestations.
pub fn workId(e: SettledEarning) [32]u8 {
    var buf: [4 + 4 + 8]u8 = undefined;
    std.mem.writeInt(u32, buf[0..4], e.node_id, .big);
    @memcpy(buf[4..8], &e.job_nonce);
    std.mem.writeInt(u64, buf[8..16], e.receipt_tag, .big);
    var out: [32]u8 = undefined;
    Sha256.hash(&buf, &out, .{});
    return out;
}

/// Build the attestation for one earning, aimed at one chain. `global_nonce`
/// must be unique across ALL chains (the relayer keeps a monotonic counter);
/// re-using it is exactly what the mint authority's spent set refuses.
pub fn buildAttestation(
    e: SettledEarning,
    chain: mint.Chain,
    global_nonce: u128,
    epoch: u32,
) mint.Attestation {
    return .{
        .worker = e.worker_address,
        .work_id = workId(e),
        .chain = chain,
        .amount_mtri = e.amount_mtri,
        .global_nonce = global_nonce,
        .epoch = epoch,
    };
}

/// In production each attestor signs remotely and returns its 64-byte signature;
/// the relayer only collects them. This models that: given the signing keys of
/// the attestors that agreed, produce their signatures over the digest. The
/// relayer never holds the mint authority — only signatures other parties made.
pub fn collectSignatures(
    allocator: std.mem.Allocator,
    att: mint.Attestation,
    signers: []const Ed25519.KeyPair,
) ![]const [64]u8 {
    const d = att.digest();
    const sigs = try allocator.alloc([64]u8, signers.len);
    for (signers, 0..) |kp, i| {
        const s = try kp.sign(&d, null);
        sigs[i] = s.toBytes();
    }
    return sigs;
}

// ---------------------------------------------------------------------------
// Tests — the whole pipeline, in software: earning -> attestation -> mint.
// ---------------------------------------------------------------------------

const testing = std.testing;

fn keys(n: usize, kp: []Ed25519.KeyPair, pk: []Ed25519.PublicKey) void {
    for (0..n) |i| {
        var seed: [Ed25519.KeyPair.seed_length]u8 = [_]u8{0} ** Ed25519.KeyPair.seed_length;
        seed[0] = @intCast(i + 1);
        const k = Ed25519.KeyPair.generateDeterministic(seed) catch unreachable;
        kp[i] = k;
        pk[i] = k.public_key;
    }
}

fn sampleEarning() SettledEarning {
    return .{
        .node_id = 0x5452494E, // "TRIN"
        .worker_address = [_]u8{0xAB} ** 32,
        .amount_mtri = 7,
        .job_nonce = [_]u8{ 1, 2, 3, 4 },
        .receipt_tag = 0xDEADBEEF,
    };
}

test "a settled earning mints through the authority" {
    var kp: [3]Ed25519.KeyPair = undefined;
    var pk: [3]Ed25519.PublicKey = undefined;
    keys(3, &kp, &pk);
    var spent = mint.SpentSet.init(testing.allocator);
    defer spent.deinit();
    var auth = mint.Authority.init(&pk, 2, .ton, 1, &spent);

    const e = sampleEarning();
    const att = buildAttestation(e, .ton, 1, 1);
    const sigs = try collectSignatures(testing.allocator, att, kp[0..2]); // 2 of 3
    defer testing.allocator.free(sigs);

    const minted = try auth.authorizeMint(att, sigs);
    try testing.expectEqual(@as(u64, 7), minted);
    try testing.expectEqualSlices(u8, &e.worker_address, &att.worker); // paid to the worker
}

test "the relayer cannot mint the same earning twice" {
    var kp: [3]Ed25519.KeyPair = undefined;
    var pk: [3]Ed25519.PublicKey = undefined;
    keys(3, &kp, &pk);
    var spent = mint.SpentSet.init(testing.allocator);
    defer spent.deinit();
    var auth = mint.Authority.init(&pk, 2, .ton, 1, &spent);

    const e = sampleEarning();
    // Re-submitting with the SAME global_nonce is refused, whatever the relayer does.
    const att = buildAttestation(e, .ton, 99, 1);
    const sigs = try collectSignatures(testing.allocator, att, kp[0..2]);
    defer testing.allocator.free(sigs);
    _ = try auth.authorizeMint(att, sigs);
    try testing.expectError(mint.Error.ReplayedNonce, auth.authorizeMint(att, sigs));
}

test "work_id differs for two different jobs of the same worker and amount" {
    var e1 = sampleEarning();
    var e2 = sampleEarning();
    e2.job_nonce = [_]u8{ 9, 9, 9, 9 }; // a different job
    try testing.expect(!std.mem.eql(u8, &workId(e1), &workId(e2)));
    // ...but the same job maps to the same work_id (deterministic binding).
    try testing.expectEqualSlices(u8, &workId(e1), &workId(sampleEarning()));
    _ = &e1;
}
