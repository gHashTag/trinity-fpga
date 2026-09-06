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
