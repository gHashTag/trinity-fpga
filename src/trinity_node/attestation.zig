// ═══════════════════════════════════════════════════════════════════════════════
// TRINITY DEPIN ATTESTATION — Bitstream Trust Anchor
//
// Makes a reproducible openXC7 bitstream a verifiable compute primitive.
// A DePIN node proves it ran a specific FPGA design by:
//   1. Computing SHA256(bitstream) = attestation key
//   2. Running a conformance vector through the FPGA
//   3. Signing the result with Ed25519
//
// Any party can independently rebuild the bitstream and verify the hash matches.
//
// Protocol: see deploy/contracts/ATTESTATION_PROTOCOL.md
//
// Agent K (Kernel/FPGA) + Agent F (Conformance) + Agent Y (Yield/DePIN)
// V = n × 3^k × π^m × φ^p × e^q
// φ² + 1/φ² = 3 = TRINITY
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");
const crypto = @import("crypto.zig");
const Ed25519 = std.crypto.sign.Ed25519;
const Sha256 = std.crypto.hash.sha2.Sha256;

// ═══════════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════════

pub const PROTOCOL_VERSION = "trinity-depin-attestation/v1";
pub const DEFAULT_TARGET_PART = "xc7a200tfbg484-2";
pub const PROVENANCE_TOOL = "hardware/tools/bitstream_provenance.py";

// ═══════════════════════════════════════════════════════════════════════════════
// HEX UTILITIES
// ═══════════════════════════════════════════════════════════════════════════════

/// Convert a byte slice to a lowercase hex string (caller owns memory).
fn toHex(allocator: std.mem.Allocator, bytes: []const u8) ![]u8 {
    const hex = try allocator.alloc(u8, bytes.len * 2);
    for (bytes, 0..) |byte, i| {
        const high = byte >> 4;
        const low = byte & 0x0F;
        hex[i * 2] = if (high < 10) '0' + high else 'a' + high - 10;
        hex[i * 2 + 1] = if (low < 10) '0' + low else 'a' + low - 10;
    }
    return hex;
}

/// Convert a [32]u8 hash to "sha256:<64hex>" (caller owns memory).
fn hashToHex(allocator: std.mem.Allocator, hash: [32]u8) ![]u8 {
    const hex = try toHex(allocator, &hash);
    defer allocator.free(hex);
    return std.fmt.allocPrint(allocator, "sha256:{s}", .{hex});
}

// ═══════════════════════════════════════════════════════════════════════════════
// PROTOCOL STRUCTURES
//
// Field names are in alphabetical order within each struct so that
// std.json.stringify produces canonical (RFC 8785 JCS-compatible) output
// with no additional sorting.
// ═══════════════════════════════════════════════════════════════════════════════

pub const ConformanceProof = struct {
    all_passed: bool,
    format: []const u8,
    operation: []const u8,
    results_hash: []const u8,
    vector_count: u32,
    vectors_hash: []const u8,
};

pub const ToolchainProvenance = struct {
    fasm_version: []const u8,
    nextpnr_commit: []const u8,
    prjxray_commit: []const u8,
    prjxray_db_commit: []const u8,
    yosys_version: []const u8,
};

pub const Attestation = struct {
    bitstream_hash: []const u8,
    conformance_proof: ConformanceProof,
    design: []const u8,
    docker_image: []const u8,
    node_public_key: []const u8,
    source_commit: []const u8,
    target_part: []const u8,
    timestamp: []const u8,
    toolchain_provenance: ToolchainProvenance,
};

pub const SignedAttestation = struct {
    attestation: Attestation,
    node_signature: []const u8,
    protocol: []const u8,
};

// ═══════════════════════════════════════════════════════════════════════════════
// BITSTREAM HASHING
// ═══════════════════════════════════════════════════════════════════════════════

/// Compute SHA256 of a bitstream file by streaming.
/// This hash is the attestation key — the cryptographic commitment to
/// (source, toolchain, routing).
pub fn computeBitstreamHash(path: []const u8) ![32]u8 {
    const file = try std.fs.cwd().openFile(path, .{});
    defer file.close();

    var hasher = Sha256.init(.{});
    var buf: [65536]u8 = undefined;
    while (true) {
        const bytes_read = try file.read(&buf);
        if (bytes_read == 0) break;
        hasher.update(buf[0..bytes_read]);
    }
    return hasher.finalResult();
}

/// Compute SHA256 of a bitstream and return as "sha256:<hex>" string.
/// Caller owns the returned slice.
pub fn computeBitstreamHashHex(allocator: std.mem.Allocator, path: []const u8) ![]u8 {
    const hash = try computeBitstreamHash(path);
    return hashToHex(allocator, hash);
}

/// Compute SHA256 of a conformance vectors file.
pub fn computeVectorsHash(allocator: std.mem.Allocator, vectors_path: []const u8) ![]u8 {
    const file = try std.fs.cwd().openFile(vectors_path, .{});
    defer file.close();

    var hasher = Sha256.init(.{});
    var buf: [65536]u8 = undefined;
    while (true) {
        const bytes_read = try file.read(&buf);
        if (bytes_read == 0) break;
        hasher.update(buf[0..bytes_read]);
    }
    const hash = hasher.finalResult();
    return hashToHex(allocator, hash);
}

/// Compute SHA256 of concatenated FPGA results (the results_hash).
/// Each result should be the raw bytes of a single operation output.
pub fn computeResultsHash(allocator: std.mem.Allocator, results: []const []const u8) ![]u8 {
    var hasher = Sha256.init(.{});
    for (results) |result| {
        hasher.update(result);
    }
    const hash = hasher.finalResult();
    return hashToHex(allocator, hash);
}

// ═══════════════════════════════════════════════════════════════════════════════
// PROVENANCE VERIFICATION
// ═══════════════════════════════════════════════════════════════════════════════

/// Verify a bitstream's provenance manifest by calling the Python tool.
/// Returns true if all source hashes and the bitstream hash match.
///
/// TODO(X): If Python is unavailable, implement a native Zig manifest parser
/// that reads the .provenance.json and re-hashes the files directly.
pub fn verifyProvenance(allocator: std.mem.Allocator, bitstream_path: []const u8) bool {
    return verifyProvenanceWithTool(allocator, bitstream_path, PROVENANCE_TOOL);
}

/// Verify provenance with an explicit path to the provenance tool.
pub fn verifyProvenanceWithTool(
    allocator: std.mem.Allocator,
    bitstream_path: []const u8,
    tool_path: []const u8,
) bool {
    const result = std.process.Child.run(.{
        .allocator = allocator,
        .argv = &.{ "python3", tool_path, "verify", bitstream_path },
        .max_output_bytes = 1024 * 1024,
    }) catch return false;
    defer allocator.free(result.stdout);
    defer allocator.free(result.stderr);

    return switch (result.term) {
        .Exited => |code| code == 0,
        else => false,
    };
}

// ═══════════════════════════════════════════════════════════════════════════════
// CANONICAL JSON SERIALIZATION (for signing)
// ═══════════════════════════════════════════════════════════════════════════════

/// Serialize an Attestation to canonical JSON (sorted keys, no whitespace).
/// This is the message that gets Ed25519-signed.
/// Caller owns the returned slice.
pub fn canonicalizeAttestation(allocator: std.mem.Allocator, att: Attestation) ![]u8 {
    var list: std.ArrayList(u8) = .empty;
    errdefer list.deinit(allocator);

    {
        var aw: std.Io.Writer.Allocating = .fromArrayList(allocator, &list);
        errdefer list = aw.toArrayList();
        const w = &aw.writer;

        try w.writeAll("{");

        // bitstream_hash
        try w.print("\"bitstream_hash\":\"{s}\"", .{att.bitstream_hash});

        // conformance_proof
        try w.writeAll(",\"conformance_proof\":{");
        try w.print("\"all_passed\":{}", .{att.conformance_proof.all_passed});
        try w.print(",\"format\":\"{s}\"", .{att.conformance_proof.format});
        try w.print(",\"operation\":\"{s}\"", .{att.conformance_proof.operation});
        try w.print(",\"results_hash\":\"{s}\"", .{att.conformance_proof.results_hash});
        try w.print(",\"vector_count\":{d}", .{att.conformance_proof.vector_count});
        try w.print(",\"vectors_hash\":\"{s}\"", .{att.conformance_proof.vectors_hash});
        try w.writeAll("}");

        // design
        try w.print(",\"design\":\"{s}\"", .{att.design});

        // docker_image
        try w.print(",\"docker_image\":\"{s}\"", .{att.docker_image});

        // node_public_key
        try w.print(",\"node_public_key\":\"{s}\"", .{att.node_public_key});

        // source_commit
        try w.print(",\"source_commit\":\"{s}\"", .{att.source_commit});

        // target_part
        try w.print(",\"target_part\":\"{s}\"", .{att.target_part});

        // timestamp
        try w.print(",\"timestamp\":\"{s}\"", .{att.timestamp});

        // toolchain_provenance
        try w.writeAll(",\"toolchain_provenance\":{");
        try w.print("\"fasm_version\":\"{s}\"", .{att.toolchain_provenance.fasm_version});
        try w.print(",\"nextpnr_commit\":\"{s}\"", .{att.toolchain_provenance.nextpnr_commit});
        try w.print(",\"prjxray_commit\":\"{s}\"", .{att.toolchain_provenance.prjxray_commit});
        try w.print(",\"prjxray_db_commit\":\"{s}\"", .{att.toolchain_provenance.prjxray_db_commit});
        try w.print(",\"yosys_version\":\"{s}\"", .{att.toolchain_provenance.yosys_version});
        try w.writeAll("}");

        try w.writeAll("}");

        list = aw.toArrayList();
    }

    return list.toOwnedSlice(allocator);
}

/// Serialize a SignedAttestation to pretty JSON (for storage / network transfer).
/// Caller owns the returned slice.
pub fn serializeSignedAttestation(allocator: std.mem.Allocator, signed: SignedAttestation) ![]u8 {
    var list: std.ArrayList(u8) = .empty;
    errdefer list.deinit(allocator);

    {
        var aw: std.Io.Writer.Allocating = .fromArrayList(allocator, &list);
        errdefer list = aw.toArrayList();
        const w = &aw.writer;

        try w.writeAll("{\n");

        // attestation
        try w.writeAll("  \"attestation\": ");
        const canon = try canonicalizeAttestation(allocator, signed.attestation);
        defer allocator.free(canon);

        // Pretty-print by adding newlines after commas at depth 1
        // (simplified: just emit compact inside the attestation key)
        try w.writeAll(canon);

        // node_signature
        try w.print(",\n  \"node_signature\": \"{s}\"", .{signed.node_signature});

        // protocol
        try w.print(",\n  \"protocol\": \"{s}\"", .{signed.protocol});

        try w.writeAll("\n}\n");

        list = aw.toArrayList();
    }

    return list.toOwnedSlice(allocator);
}

// ═══════════════════════════════════════════════════════════════════════════════
// ATTESTATION CREATION & SIGNING
// ═══════════════════════════════════════════════════════════════════════════════

/// Create an unsigned Attestation for a bitstream.
///
/// `bitstream_path`   — path to the .bit file
/// `format`           — e.g. "gf16"
/// `operation`         — e.g. "add"
/// `results_hash`      — SHA256 of FPGA results, as "sha256:<hex>"
/// `vectors_hash`      — SHA256 of the conformance vectors file, as "sha256:<hex>"
/// `vector_count`      — number of vectors tested
/// `all_passed`        — whether all vectors passed
/// `toolchain`         — toolchain provenance info
/// `keypair`           — node's Ed25519 keypair (for public key)
///
/// Caller owns all string fields (allocated via `allocator`).
pub fn createAttestation(
    allocator: std.mem.Allocator,
    bitstream_path: []const u8,
    design: []const u8,
    format: []const u8,
    operation: []const u8,
    results_hash: []const u8,
    vectors_hash: []const u8,
    vector_count: u32,
    all_passed: bool,
    toolchain: ToolchainProvenance,
    keypair: *const crypto.KeyPair,
) !Attestation {
    // Compute bitstream hash
    const bit_hash = try computeBitstreamHash(bitstream_path);
    const bit_hash_str = try hashToHex(allocator, bit_hash);

    // Node public key as hex
    const pubkey_hex = try toHex(allocator, &keypair.public_key);
    const pubkey_str = try std.fmt.allocPrint(allocator, "ed25519:{s}", .{pubkey_hex});
    allocator.free(pubkey_hex);

    // Git commit
    const git_commit = getGitCommit(allocator) catch try allocator.dupe(u8, "git:unknown");

    // Timestamp (UTC, ISO 8601)
    const timestamp = try getTimestamp(allocator);

    return Attestation{
        .bitstream_hash = bit_hash_str,
        .conformance_proof = .{
            .all_passed = all_passed,
            .format = try allocator.dupe(u8, format),
            .operation = try allocator.dupe(u8, operation),
            .results_hash = try allocator.dupe(u8, results_hash),
            .vector_count = vector_count,
            .vectors_hash = try allocator.dupe(u8, vectors_hash),
        },
        .design = try allocator.dupe(u8, design),
        .docker_image = try allocator.dupe(u8, "trinity-openxc7-pinned"),
        .node_public_key = pubkey_str,
        .source_commit = git_commit,
        .target_part = try allocator.dupe(u8, DEFAULT_TARGET_PART),
        .timestamp = timestamp,
        .toolchain_provenance = .{
            .fasm_version = try allocator.dupe(u8, toolchain.fasm_version),
            .nextpnr_commit = try allocator.dupe(u8, toolchain.nextpnr_commit),
            .prjxray_commit = try allocator.dupe(u8, toolchain.prjxray_commit),
            .prjxray_db_commit = try allocator.dupe(u8, toolchain.prjxray_db_commit),
            .yosys_version = try allocator.dupe(u8, toolchain.yosys_version),
        },
    };
}

/// Sign an attestation with the node's Ed25519 private key.
/// Returns a SignedAttestation with the signature filled in.
/// Caller owns the signature string (allocated via `allocator`).
pub fn signAttestation(
    allocator: std.mem.Allocator,
    attestation: Attestation,
    keypair: *const crypto.KeyPair,
) !SignedAttestation {
    // Canonicalize the attestation for signing
    const message = try canonicalizeAttestation(allocator, attestation);
    defer allocator.free(message);

    // Sign with Ed25519
    const sig_bytes = keypair.sign(message);

    // Encode signature as hex
    const sig_hex = try toHex(allocator, &sig_bytes);
    const sig_str = try std.fmt.allocPrint(allocator, "ed25519:{s}", .{sig_hex});
    allocator.free(sig_hex);

    return SignedAttestation{
        .attestation = attestation,
        .node_signature = sig_str,
        .protocol = try allocator.dupe(u8, PROTOCOL_VERSION),
    };
}

/// Verify a signed attestation's Ed25519 signature.
/// Re-canonicalizes the attestation and checks the signature.
pub fn verifyAttestation(
    allocator: std.mem.Allocator,
    signed: SignedAttestation,
    expected_public_key: [32]u8,
) bool {
    // Re-canonicalize the attestation
    const message = canonicalizeAttestation(allocator, signed.attestation) catch return false;
    defer allocator.free(message);

    // Decode the signature from hex (strip "ed25519:" prefix)
    const sig_str = signed.node_signature;
    var sig_bytes: [64]u8 = undefined;
    if (!parseHexSig(sig_str, &sig_bytes)) return false;

    // Verify using crypto.zig KeyPair.verify
    return crypto.KeyPair.verify(expected_public_key, message, sig_bytes);
}

/// Convenience: verify a signed attestation using the public key embedded in it.
pub fn verifyAttestationSelfSigned(
    allocator: std.mem.Allocator,
    signed: SignedAttestation,
) bool {
    // Extract public key from attestation
    var pubkey: [32]u8 = undefined;
    if (!parseHexPubKey(signed.attestation.node_public_key, &pubkey)) return false;
    return verifyAttestation(allocator, signed, pubkey);
}

// ═══════════════════════════════════════════════════════════════════════════════
// PERSISTENCE
// ═══════════════════════════════════════════════════════════════════════════════

/// Write a signed attestation to a JSON file.
pub fn writeSignedAttestation(
    allocator: std.mem.Allocator,
    signed: SignedAttestation,
    path: []const u8,
) !void {
    const json = try serializeSignedAttestation(allocator, signed);
    defer allocator.free(json);

    try std.fs.cwd().writeFile(.{ .sub_path = path, .data = json });
}

// ═══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

/// Parse a hex-encoded Ed25519 signature string ("ed25519:<128hex>") into bytes.
fn parseHexSig(sig_str: []const u8, out: *[64]u8) bool {
    const prefix = "ed25519:";
    if (!std.mem.startsWith(u8, sig_str, prefix)) return false;
    const hex = sig_str[prefix.len..];
    if (hex.len != 128) return false;
    _ = std.fmt.hexToBytes(out[0..], hex) catch return false;
    return true;
}

/// Parse a hex-encoded Ed25519 public key string ("ed25519:<64hex>") into bytes.
fn parseHexPubKey(pubkey_str: []const u8, out: *[32]u8) bool {
    const prefix = "ed25519:";
    if (!std.mem.startsWith(u8, pubkey_str, prefix)) return false;
    const hex = pubkey_str[prefix.len..];
    if (hex.len != 64) return false;
    _ = std.fmt.hexToBytes(out[0..], hex) catch return false;
    return true;
}

/// Get the current git commit (best-effort).
fn getGitCommit(allocator: std.mem.Allocator) ![]u8 {
    const result = std.process.Child.run(.{
        .allocator = allocator,
        .argv = &.{ "git", "rev-parse", "--short=12", "HEAD" },
        .max_output_bytes = 256,
    }) catch return try allocator.dupe(u8, "git:unknown");
    defer allocator.free(result.stdout);
    defer allocator.free(result.stderr);

    const code = switch (result.term) {
        .Exited => |c| c,
        else => return try allocator.dupe(u8, "git:unknown"),
    };
    if (code != 0) return try allocator.dupe(u8, "git:unknown");

    const trimmed = std.mem.trim(u8, result.stdout, " \n\r\t");
    return std.fmt.allocPrint(allocator, "git:{s}", .{trimmed});
}

/// Get the current UTC timestamp as ISO 8601.
fn getTimestamp(allocator: std.mem.Allocator) ![]u8 {
    const ts: i64 = std.time.timestamp();
    const epoch_secs: u64 = @intCast(@max(ts, 0));

    const es = std.time.epoch.EpochSeconds{ .secs = epoch_secs };
    const day = es.getEpochDay();
    const year_day = day.calculateYearDay();
    const month_day = year_day.calculateMonthDay();
    const ds = es.getDaySeconds();

    return std.fmt.allocPrint(allocator, "{d}-{d:0>2}-{d:0>2}T{d:0>2}:{d:0>2}:{d:0>2}Z", .{
        year_day.year,
        month_day.month.numeric(),
        month_day.day_index + 1,
        ds.getHoursIntoDay(),
        ds.getMinutesIntoHour(),
        ds.getSecondsIntoMinute(),
    });
}

/// Free all heap-allocated strings in an Attestation.
pub fn freeAttestation(allocator: std.mem.Allocator, att: Attestation) void {
    allocator.free(att.bitstream_hash);
    allocator.free(att.conformance_proof.format);
    allocator.free(att.conformance_proof.operation);
    allocator.free(att.conformance_proof.results_hash);
    allocator.free(att.conformance_proof.vectors_hash);
    allocator.free(att.design);
    allocator.free(att.docker_image);
    allocator.free(att.node_public_key);
    allocator.free(att.source_commit);
    allocator.free(att.target_part);
    allocator.free(att.timestamp);
    allocator.free(att.toolchain_provenance.fasm_version);
    allocator.free(att.toolchain_provenance.nextpnr_commit);
    allocator.free(att.toolchain_provenance.prjxray_commit);
    allocator.free(att.toolchain_provenance.prjxray_db_commit);
    allocator.free(att.toolchain_provenance.yosys_version);
}

/// Free all heap-allocated strings in a SignedAttestation.
pub fn freeSignedAttestation(allocator: std.mem.Allocator, signed: SignedAttestation) void {
    freeAttestation(allocator, signed.attestation);
    allocator.free(signed.node_signature);
    allocator.free(signed.protocol);
}

// ═══════════════════════════════════════════════════════════════════════════════
// DEFAULT TOOLCHAIN (from the pinned Dockerfile)
// ═══════════════════════════════════════════════════════════════════════════════

pub fn defaultToolchain() ToolchainProvenance {
    return .{
        .yosys_version = "0.63",
        .nextpnr_commit = "unknown",
        .prjxray_commit = "unknown",
        .prjxray_db_commit = "unknown",
        .fasm_version = "0.0.2.post0",
    };
}

// ═══════════════════════════════════════════════════════════════════════════════
// TESTS
// ═══════════════════════════════════════════════════════════════════════════════

test "compute bitstream hash of known data" {
    const tmp = "test_bitstream_hash.tmp";
    defer std.fs.cwd().deleteFile(tmp) catch {};

    // Write known data
    const data = "Trinity DePIN Trust Anchor";
    try std.fs.cwd().writeFile(.{ .sub_path = tmp, .data = data });

    const hash = try computeBitstreamHash(tmp);
    const expected = crypto.sha256(data);
    try std.testing.expectEqualSlices(u8, &expected, &hash);
}

test "hex encoding roundtrip" {
    const allocator = std.testing.allocator;
    const bytes = [_]u8{ 0x00, 0xff, 0xab, 0x42 };
    const hex = try toHex(allocator, &bytes);
    defer allocator.free(hex);
    try std.testing.expectEqualStrings("00ffab42", hex);
}

test "hash to hex string format" {
    const allocator = std.testing.allocator;
    var hash: [32]u8 = undefined;
    @memset(&hash, 0xAB);
    const str = try hashToHex(allocator, hash);
    defer allocator.free(str);
    try std.testing.expect(std.mem.startsWith(u8, str, "sha256:"));
    try std.testing.expectEqual(@as(usize, 8 + 64), str.len);
}

test "canonicalize attestation is deterministic" {
    const allocator = std.testing.allocator;

    const att = Attestation{
        .bitstream_hash = "sha256:abc123",
        .conformance_proof = .{
            .all_passed = true,
            .format = "gf16",
            .operation = "add",
            .results_hash = "sha256:def456",
            .vector_count = 10,
            .vectors_hash = "sha256:ghi789",
        },
        .design = "test_design",
        .docker_image = "trinity-openxc7-pinned",
        .node_public_key = "ed25519:pubkeyhex",
        .source_commit = "git:abc123",
        .target_part = "xc7a200tfbg484-2",
        .timestamp = "2026-01-01T00:00:00Z",
        .toolchain_provenance = .{
            .fasm_version = "0.0.2.post0",
            .nextpnr_commit = "nextpnr123",
            .prjxray_commit = "prjxray456",
            .prjxray_db_commit = "db789",
            .yosys_version = "0.63",
        },
    };

    const canon1 = try canonicalizeAttestation(allocator, att);
    defer allocator.free(canon1);
    const canon2 = try canonicalizeAttestation(allocator, att);
    defer allocator.free(canon2);

    try std.testing.expectEqualStrings(canon1, canon2);
}

test "sign and verify attestation roundtrip" {
    const allocator = std.testing.allocator;
    const kp = crypto.KeyPair.generate();

    const att = Attestation{
        .bitstream_hash = "sha256:deadbeef",
        .conformance_proof = .{
            .all_passed = true,
            .format = "gf16",
            .operation = "add",
            .results_hash = "sha256:results1",
            .vector_count = 42,
            .vectors_hash = "sha256:vectors1",
        },
        .design = "corona_compute_gf16_add_ax7203",
        .docker_image = "trinity-openxc7-pinned",
        .node_public_key = blk: {
            const hex = try toHex(allocator, &kp.public_key);
            defer allocator.free(hex);
            break :blk try std.fmt.allocPrint(allocator, "ed25519:{s}", .{hex});
        },
        .source_commit = "git:abc123",
        .target_part = "xc7a200tfbg484-2",
        .timestamp = "2026-07-14T12:00:00Z",
        .toolchain_provenance = .{
            .fasm_version = "0.0.2.post0",
            .nextpnr_commit = "abc",
            .prjxray_commit = "def",
            .prjxray_db_commit = "ghi",
            .yosys_version = "0.63",
        },
    };

    // Sign
    var signed = try signAttestation(allocator, att, &kp);

    // Verify (with correct public key)
    try std.testing.expect(verifyAttestation(allocator, signed, kp.public_key));

    // Verify with wrong public key should fail
    const wrong_kp = crypto.KeyPair.generate();
    try std.testing.expect(!verifyAttestation(allocator, signed, wrong_kp.public_key));

    // Self-verify (using public key embedded in attestation)
    try std.testing.expect(verifyAttestationSelfSigned(allocator, signed));

    // Tamper: change bitstream_hash, should fail verification
    signed.attestation.bitstream_hash = "sha256:tampered";
    try std.testing.expect(!verifyAttestation(allocator, signed, kp.public_key));

    freeSignedAttestation(allocator, signed);
}

test "compute results hash" {
    const allocator = std.testing.allocator;
    const results = [_][]const u8{ "result1", "result2", "result3" };
    const hash_str = try computeResultsHash(allocator, &results);
    defer allocator.free(hash_str);
    try std.testing.expect(std.mem.startsWith(u8, hash_str, "sha256:"));

    // Verify it matches manual computation
    var hasher = Sha256.init(.{});
    hasher.update("result1");
    hasher.update("result2");
    hasher.update("result3");
    const expected = hasher.finalResult();
    const expected_hex = try hashToHex(allocator, expected);
    defer allocator.free(expected_hex);
    try std.testing.expectEqualStrings(expected_hex, hash_str);
}

test "parse hex signature roundtrip" {
    const allocator = std.testing.allocator;
    const kp = crypto.KeyPair.generate();
    const msg = "test message";
    const sig = kp.sign(msg);

    const hex = try toHex(allocator, &sig);
    defer allocator.free(hex);
    const sig_str = try std.fmt.allocPrint(allocator, "ed25519:{s}", .{hex});
    defer allocator.free(sig_str);

    var parsed: [64]u8 = undefined;
    try std.testing.expect(parseHexSig(sig_str, &parsed));
    try std.testing.expectEqualSlices(u8, &sig, &parsed);
}

test "serialize signed attestation to JSON" {
    const allocator = std.testing.allocator;
    const kp = crypto.KeyPair.generate();

    const pubkey_hex = try toHex(allocator, &kp.public_key);
    defer allocator.free(pubkey_hex);
    const pubkey_str = try std.fmt.allocPrint(allocator, "ed25519:{s}", .{pubkey_hex});
    defer allocator.free(pubkey_str);

    const att = Attestation{
        .bitstream_hash = "sha256:test",
        .conformance_proof = .{
            .all_passed = true,
            .format = "gf8",
            .operation = "mul",
            .results_hash = "sha256:res",
            .vector_count = 5,
            .vectors_hash = "sha256:vec",
        },
        .design = "test",
        .docker_image = "img",
        .node_public_key = pubkey_str,
        .source_commit = "git:test",
        .target_part = "part",
        .timestamp = "2026-01-01T00:00:00Z",
        .toolchain_provenance = .{
            .fasm_version = "1",
            .nextpnr_commit = "2",
            .prjxray_commit = "3",
            .prjxray_db_commit = "4",
            .yosys_version = "5",
        },
    };

    const signed = try signAttestation(allocator, att, &kp);
    defer freeSignedAttestation(allocator, signed);

    const json = try serializeSignedAttestation(allocator, signed);
    defer allocator.free(json);

    // Should contain protocol version
    try std.testing.expect(std.mem.indexOf(u8, json, PROTOCOL_VERSION) != null);
    // Should contain node_signature
    try std.testing.expect(std.mem.indexOf(u8, json, "node_signature") != null);
    // Should contain bitstream_hash
    try std.testing.expect(std.mem.indexOf(u8, json, "bitstream_hash") != null);
}
