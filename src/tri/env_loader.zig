// @origin(manual) @regen(pending)
// env_loader.zig — Load .env into process environment at startup
// Silently skips if .env not found. Process env always wins over .env values.

const std = @import("std");

const c = struct {
    extern "c" fn setenv(name: [*:0]const u8, value: [*:0]const u8, overwrite: c_int) c_int;
    // 0.16 removed std.posix.getenv. Its documented replacement,
    // std.process.Environ, is a value only process.Init supplies, which would
    // push an Init through every caller of loadDotEnv. libc is already linked
    // here for setenv and getenv is its exact counterpart, so the pair stays
    // symmetrical and callers are asked for nothing.
    extern "c" fn getenv(name: [*:0]const u8) ?[*:0]const u8;
};

/// Parse a single .env line into key and value, or null if comment/blank/invalid.
pub fn parseLine(line: []const u8) ?struct { key: []const u8, value: []const u8 } {
    // Skip leading whitespace
    var s = std.mem.trimStart(u8, line, " \t");

    // Skip empty lines and comments
    if (s.len == 0 or s[0] == '#') return null;

    // Skip optional "export " prefix
    if (std.mem.startsWith(u8, s, "export ")) {
        s = s["export ".len..];
        s = std.mem.trimStart(u8, s, " \t");
    }

    // Find '='
    const eq = std.mem.indexOfScalar(u8, s, '=') orelse return null;
    const key = std.mem.trimEnd(u8, s[0..eq], " \t");
    if (key.len == 0) return null;

    var value = std.mem.trimStart(u8, s[eq + 1 ..], " \t");
    value = std.mem.trimEnd(u8, value, " \t\r");

    // Strip matching quotes
    if (value.len >= 2) {
        const first = value[0];
        const last = value[value.len - 1];
        if ((first == '"' and last == '"') or (first == '\'' and last == '\'')) {
            value = value[1 .. value.len - 1];
        }
    }

    return .{ .key = key, .value = value };
}

/// Load .env from CWD into process environment. Process env takes precedence.
/// Silently returns if .env is missing or unreadable.
/// Takes an `io`: 0.16 moved file I/O behind it, and that is a signature change
/// rather than a rename -- every caller must have one to give.
pub fn loadDotEnv(io: std.Io, allocator: std.mem.Allocator) void {
    // readFileAlloc replaces open + readToEndAlloc + close: the whole-file read
    // lives on the directory in 0.16, not on the file.
    const content = std.Io.Dir.cwd().readFileAlloc(io, ".env", allocator, .limited(32 * 1024)) catch return;
    // intentionally leaked — process-lifetime data

    var iter = std.mem.splitScalar(u8, content, '\n');
    while (iter.next()) |line| {
        const parsed = parseLine(line) orelse continue;

        // Skip if already set in process environment
        // getenv needs a null-terminated name and setenv below needs one too,
        // so the single dupeZ serves both.
        const key_z = allocator.dupeZ(u8, parsed.key) catch continue;
        if (c.getenv(key_z.ptr) != null) continue;

        // intentionally leaked — process-lifetime data
        const val_z = allocator.dupeZ(u8, parsed.value) catch continue;

        _ = c.setenv(key_z.ptr, val_z.ptr, 0);
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════════

test "parseLine: basic KEY=VALUE" {
    const r = parseLine("FOO=bar").?;
    try std.testing.expectEqualStrings("FOO", r.key);
    try std.testing.expectEqualStrings("bar", r.value);
}

test "parseLine: quoted value" {
    const r = parseLine("KEY=\"hello world\"").?;
    try std.testing.expectEqualStrings("KEY", r.key);
    try std.testing.expectEqualStrings("hello world", r.value);
}

test "parseLine: single quoted" {
    const r = parseLine("K='val'").?;
    try std.testing.expectEqualStrings("val", r.value);
}

test "parseLine: skip comment" {
    try std.testing.expect(parseLine("# this is a comment") == null);
}

test "parseLine: skip blank" {
    try std.testing.expect(parseLine("") == null);
    try std.testing.expect(parseLine("   ") == null);
}

test "parseLine: export prefix" {
    const r = parseLine("export MY_VAR=123").?;
    try std.testing.expectEqualStrings("MY_VAR", r.key);
    try std.testing.expectEqualStrings("123", r.value);
}

test "parseLine: no equals sign" {
    try std.testing.expect(parseLine("NOEQUALS") == null);
}

test "parseLine: empty value" {
    const r = parseLine("EMPTY=").?;
    try std.testing.expectEqualStrings("EMPTY", r.key);
    try std.testing.expectEqualStrings("", r.value);
}

test "parseLine: spaces around equals" {
    const r = parseLine("KEY = value").?;
    try std.testing.expectEqualStrings("KEY", r.key);
    try std.testing.expectEqualStrings("value", r.value);
}

test "parseLine: carriage return trimmed" {
    const r = parseLine("KEY=value\r").?;
    try std.testing.expectEqualStrings("value", r.value);
}
