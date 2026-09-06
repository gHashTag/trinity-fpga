// ═══════════════════════════════════════════════════════════════════════════════
// TRI CLI - Environment variable access (Zig 0.16 shim)
// ═══════════════════════════════════════════════════════════════════════════════
//
// Zig 0.16 removed `std.process.getEnvVarOwned` and `std.posix.getenv`. The
// documented replacement is `std.process.Environ`, which is a value only
// `std.process.Init` supplies -- taking that route would mean threading an
// Environ through all 49 call sites in `src/tri`, and through every function
// between them and main.
//
// libc is already linked for this binary (the build passes -lc), and getenv is
// the exact counterpart of the function that was removed. Declaring it here
// once keeps the change at each call site to a single word: replace
// `std.process.getEnvVarOwned` with `tri_env.getEnvVarOwned`.
//
// The signature and error set below deliberately mirror the removed stdlib
// function so that existing `catch null` and `catch |err|` clauses keep their
// meaning without being rewritten.
//
// phi^2 + 1/phi^2 = 3 = TRINITY
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");

const c = struct {
    extern "c" fn getenv(name: [*:0]const u8) ?[*:0]const u8;

    /// POSIX's environment block: a null-terminated array of "KEY=VALUE"
    /// strings. `std.process.Environ` gets the same data from `process.Init`;
    /// reading it here keeps `getEnvMap` callable from anywhere, which is the
    /// whole point of this module.
    extern "c" var environ: [*:null]?[*:0]u8;
};

/// Mirrors the error set of the removed `std.process.GetEnvVarOwnedError`.
/// `InvalidWtf8` is retained for source compatibility with callers that switch
/// on it; this implementation never returns it, because POSIX environment
/// values are bytes and are handed back unvalidated.
pub const GetEnvVarOwnedError = error{
    OutOfMemory,
    EnvironmentVariableNotFound,
    InvalidWtf8,
};

/// Caller owns the returned memory. Same contract as the 0.15
/// `std.process.getEnvVarOwned`.
pub fn getEnvVarOwned(allocator: std.mem.Allocator, key: []const u8) GetEnvVarOwnedError![]u8 {
    const value = getEnvVar(allocator, key) orelse return error.EnvironmentVariableNotFound;
    return allocator.dupe(u8, value) catch return error.OutOfMemory;
}

/// Borrowed view of the variable, valid until the next `setenv` for this key.
/// Returns null when unset. Use this when the value is only read and the
/// allocation in `getEnvVarOwned` would be pure overhead.
///
/// The allocator is needed only to build the null-terminated key that getenv
/// requires; the returned slice points into the process environment, not into
/// allocator memory.
pub fn getEnvVar(allocator: std.mem.Allocator, key: []const u8) ?[]const u8 {
    const key_z = allocator.dupeZ(u8, key) catch return null;
    defer allocator.free(key_z);
    const raw = c.getenv(key_z.ptr) orelse return null;
    return std.mem.span(raw);
}

/// True when the variable is set and non-empty. The common case in this CLI is
/// a feature flag or an API key whose empty value should count as absent.
pub fn has(allocator: std.mem.Allocator, key: []const u8) bool {
    const v = getEnvVar(allocator, key) orelse return false;
    return v.len > 0;
}

/// Replaces the removed `std.process.hasEnvVarConstant`. Needs no allocator
/// because a Zig string literal is already null-terminated, so the key can go
/// straight to getenv.
///
/// Note the difference from `has` above: this reports mere EXISTENCE, matching
/// the stdlib function it replaces. A variable set to the empty string is
/// `true` here and `false` for `has`.
pub fn hasConstant(comptime key: [:0]const u8) bool {
    return c.getenv(key.ptr) != null;
}

/// Replaces the removed `std.posix.getenv`. Takes a runtime name and needs no
/// allocator: the name is copied into a stack buffer to null-terminate it for
/// libc. Names longer than the buffer return null, which is the same answer
/// the caller gets for "not set" -- no environment variable name in this tree
/// comes close.
pub fn getPosix(name: []const u8) ?[]const u8 {
    var buf: [256]u8 = undefined;
    if (name.len >= buf.len) return null;
    @memcpy(buf[0..name.len], name);
    buf[name.len] = 0;
    const raw = c.getenv(@ptrCast(&buf)) orelse return null;
    return std.mem.span(raw);
}

/// Replaces the removed `std.process.getEnvMap`. Returns a copy of the current
/// environment as a `std.process.Environ.Map`, which is what
/// `tri_proc.run`'s `env_map` field wants.
///
/// Caller owns the map and must `deinit` it, exactly as before.
///
/// Entries with no '=' are skipped rather than guessed at, and a key that
/// `Environ.Map` rejects (the empty key, or one containing '=') is skipped
/// too -- `put` asserts on those, and inheriting a malformed entry from the
/// parent environment is not worth a panic.
pub fn getEnvMap(allocator: std.mem.Allocator) std.mem.Allocator.Error!std.process.Environ.Map {
    var map: std.process.Environ.Map = .init(allocator);
    errdefer map.deinit();

    var i: usize = 0;
    while (c.environ[i]) |entry| : (i += 1) {
        const pair = std.mem.span(entry);
        const eq = std.mem.indexOfScalar(u8, pair, '=') orelse continue;
        const key = pair[0..eq];
        if (key.len == 0) continue;
        try map.put(key, pair[eq + 1 ..]);
    }
    return map;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════════

const c_test = struct {
    extern "c" fn setenv(name: [*:0]const u8, value: [*:0]const u8, overwrite: c_int) c_int;
    extern "c" fn unsetenv(name: [*:0]const u8) c_int;
};

test "getEnvVarOwned returns the value and the caller owns it" {
    const a = std.testing.allocator;
    _ = c_test.setenv("TRI_ENV_TEST_A", "hello", 1);
    defer _ = c_test.unsetenv("TRI_ENV_TEST_A");

    const v = try getEnvVarOwned(a, "TRI_ENV_TEST_A");
    defer a.free(v);
    try std.testing.expectEqualStrings("hello", v);
}

test "getEnvVarOwned reports missing variables as EnvironmentVariableNotFound" {
    const a = std.testing.allocator;
    _ = c_test.unsetenv("TRI_ENV_TEST_MISSING");
    try std.testing.expectError(
        error.EnvironmentVariableNotFound,
        getEnvVarOwned(a, "TRI_ENV_TEST_MISSING"),
    );
}

test "getEnvVar borrows without allocating a copy" {
    const a = std.testing.allocator;
    _ = c_test.setenv("TRI_ENV_TEST_B", "borrowed", 1);
    defer _ = c_test.unsetenv("TRI_ENV_TEST_B");

    const v = getEnvVar(a, "TRI_ENV_TEST_B").?;
    try std.testing.expectEqualStrings("borrowed", v);
}

test "getEnvVar returns null when unset" {
    const a = std.testing.allocator;
    _ = c_test.unsetenv("TRI_ENV_TEST_C");
    try std.testing.expect(getEnvVar(a, "TRI_ENV_TEST_C") == null);
}

test "has treats an empty value as absent" {
    const a = std.testing.allocator;
    _ = c_test.setenv("TRI_ENV_TEST_D", "", 1);
    defer _ = c_test.unsetenv("TRI_ENV_TEST_D");
    try std.testing.expect(!has(a, "TRI_ENV_TEST_D"));

    _ = c_test.setenv("TRI_ENV_TEST_D", "x", 1);
    try std.testing.expect(has(a, "TRI_ENV_TEST_D"));
}

test "catch null keeps working for optional keys" {
    const a = std.testing.allocator;
    _ = c_test.unsetenv("TRI_ENV_TEST_E");
    const v = getEnvVarOwned(a, "TRI_ENV_TEST_E") catch null;
    try std.testing.expect(v == null);
}

test "hasConstant reports existence, including an empty value" {
    _ = c_test.setenv("TRI_ENV_TEST_F", "", 1);
    defer _ = c_test.unsetenv("TRI_ENV_TEST_F");

    // The distinction from `has` is the whole point of the two functions:
    // hasEnvVarConstant asked "is it set", not "is it non-empty".
    try std.testing.expect(hasConstant("TRI_ENV_TEST_F"));
    try std.testing.expect(!has(std.testing.allocator, "TRI_ENV_TEST_F"));
}

test "hasConstant is false for an unset variable" {
    _ = c_test.unsetenv("TRI_ENV_TEST_G");
    try std.testing.expect(!hasConstant("TRI_ENV_TEST_G"));
}

test "getEnvMap copies the current environment" {
    const a = std.testing.allocator;
    _ = c_test.setenv("TRI_ENV_TEST_MAP", "in-the-map", 1);
    defer _ = c_test.unsetenv("TRI_ENV_TEST_MAP");

    var map = try getEnvMap(a);
    defer map.deinit();

    try std.testing.expectEqualStrings("in-the-map", map.get("TRI_ENV_TEST_MAP").?);
    // PATH is present in any reasonable environment; catches an empty walk.
    try std.testing.expect(map.count() > 1);
}

test "getEnvMap result is independent of later setenv" {
    const a = std.testing.allocator;
    _ = c_test.setenv("TRI_ENV_TEST_MAP2", "before", 1);
    defer _ = c_test.unsetenv("TRI_ENV_TEST_MAP2");

    var map = try getEnvMap(a);
    defer map.deinit();

    // The map owns copies, as std.process.getEnvMap did. If it held pointers
    // into the environment block, this setenv could change what it reports.
    _ = c_test.setenv("TRI_ENV_TEST_MAP2", "after", 1);
    try std.testing.expectEqualStrings("before", map.get("TRI_ENV_TEST_MAP2").?);
}

test "a value containing '=' survives the split" {
    const a = std.testing.allocator;
    _ = c_test.setenv("TRI_ENV_TEST_EQ", "a=b=c", 1);
    defer _ = c_test.unsetenv("TRI_ENV_TEST_EQ");

    var map = try getEnvMap(a);
    defer map.deinit();
    // Split on the FIRST '=' only -- the rest belongs to the value.
    try std.testing.expectEqualStrings("a=b=c", map.get("TRI_ENV_TEST_EQ").?);
}

test "getPosix reads a runtime-named variable without an allocator" {
    _ = c_test.setenv("TRI_ENV_TEST_POSIX", "value", 1);
    defer _ = c_test.unsetenv("TRI_ENV_TEST_POSIX");

    const name: []const u8 = "TRI_ENV_TEST_POSIX"; // runtime slice, not a literal
    try std.testing.expectEqualStrings("value", getPosix(name).?);
}

test "getPosix returns null when unset and for an over-long name" {
    _ = c_test.unsetenv("TRI_ENV_TEST_POSIX2");
    try std.testing.expect(getPosix("TRI_ENV_TEST_POSIX2") == null);
    try std.testing.expect(getPosix("X" ** 300) == null);
}
