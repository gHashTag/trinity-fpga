// ═══════════════════════════════════════════════════════════════════════════════
// TRI CLI - Child process execution (Zig 0.16 shim)
// ═══════════════════════════════════════════════════════════════════════════════
//
// `std.process.Child.run` is gone in Zig 0.16. The functionality is not --
// it moved to `std.process.run(gpa, io, options)` and changed shape:
//
//   * the allocator moved from a struct field to a positional parameter
//   * an `io` parameter appeared
//   * `max_output_bytes: usize` split into `stdout_limit` / `stderr_limit`,
//     both `Io.Limit` rather than plain integers
//   * `cwd: ?[]const u8` became `cwd: Child.Cwd`, a union
//   * `env_map` was renamed `environ_map`
//
// There are 279 call sites of the old form in this tree, and they use exactly
// five of the old fields: allocator, argv, max_output_bytes, cwd, env_map.
// This shim accepts that old shape and translates, so each call site changes
// by one word: `std.process.Child.run(` becomes `tri_proc.run(`.
//
// `RunResult` is unchanged between the two versions (term, stdout, stderr), so
// nothing downstream of a call site needs touching, and the caller still owns
// result.stdout and result.stderr.
//
// The `io` comes from tri_io, for the same reason described there: these call
// sites are spread across modules whose signatures would otherwise all have to
// change. A caller that already has an `io` should prefer `runIo` below and
// pass it explicitly.
//
// phi^2 + 1/phi^2 = 3 = TRINITY
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");
const tri_io = @import("tri_io");

/// Unchanged between 0.15 and 0.16: { term, stdout, stderr }.
pub const RunResult = std.process.RunResult;
pub const RunError = std.process.RunError;
pub const Term = std.process.Child.Term;

/// The 0.15 `Child.RunOptions`, kept so call sites do not have to change
/// shape. Only the fields this codebase actually uses are carried over;
/// anything else was never passed here and would be dead surface.
pub const RunOptions = struct {
    allocator: std.mem.Allocator,
    argv: []const []const u8,
    /// 0.15 semantics: a single cap applied to stdout and stderr alike.
    /// Translated into the two separate Io.Limit fields 0.16 wants.
    max_output_bytes: usize = 50 * 1024,
    /// 0.15 took a path or null-for-inherit; 0.16 takes a union.
    cwd: ?[]const u8 = null,
    env_map: ?*const std.process.Environ.Map = null,
};

/// Drop-in for the removed `std.process.Child.run`.
pub fn run(options: RunOptions) RunError!RunResult {
    return runIo(tri_io.get(), options);
}

/// Same, but with an explicit Io. Prefer this wherever one is already in
/// scope -- reaching for the ambient handle when a parameter is available
/// defeats the point of the migration.
pub fn runIo(io: std.Io, options: RunOptions) RunError!RunResult {
    return std.process.run(options.allocator, io, .{
        .argv = options.argv,
        // One cap became two. Applying the old single value to each stream
        // separately matches the old behaviour for every call site here,
        // which used it as "do not let this run away", not as a combined
        // budget across both streams.
        .stdout_limit = .limited(options.max_output_bytes),
        .stderr_limit = .limited(options.max_output_bytes),
        .cwd = if (options.cwd) |p| .{ .path = p } else .inherit,
        .environ_map = options.env_map,
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════════

test "run captures stdout and a clean exit code" {
    const a = std.testing.allocator;
    const r = try run(.{
        .allocator = a,
        .argv = &.{ "/bin/echo", "trinity" },
    });
    defer a.free(r.stdout);
    defer a.free(r.stderr);

    try std.testing.expectEqualStrings("trinity\n", r.stdout);
    try std.testing.expect(r.term == .exited);
    try std.testing.expectEqual(@as(u8, 0), r.term.exited);
}

test "a non-zero exit is reported in term, not as an error" {
    // The old API returned normally here and put the status in `term`. Code in
    // this tree branches on that, so a shim that turned it into an error would
    // change control flow at every call site.
    const a = std.testing.allocator;
    const r = try run(.{
        .allocator = a,
        .argv = &.{ "/bin/sh", "-c", "exit 3" },
    });
    defer a.free(r.stdout);
    defer a.free(r.stderr);

    try std.testing.expect(r.term == .exited);
    try std.testing.expectEqual(@as(u8, 3), r.term.exited);
}

test "stderr is captured separately from stdout" {
    const a = std.testing.allocator;
    const r = try run(.{
        .allocator = a,
        .argv = &.{ "/bin/sh", "-c", "echo out; echo err 1>&2" },
    });
    defer a.free(r.stdout);
    defer a.free(r.stderr);

    try std.testing.expectEqualStrings("out\n", r.stdout);
    try std.testing.expectEqualStrings("err\n", r.stderr);
}

test "cwd is honoured when given as a path" {
    const a = std.testing.allocator;
    const r = try run(.{
        .allocator = a,
        .argv = &.{"/bin/pwd"},
        .cwd = "/tmp",
    });
    defer a.free(r.stdout);
    defer a.free(r.stderr);

    // /tmp is a symlink to /private/tmp on Darwin, so match either.
    const out = std.mem.trimEnd(u8, r.stdout, "\n");
    try std.testing.expect(std.mem.endsWith(u8, out, "/tmp"));
}

test "cwd defaults to inherit when null" {
    const a = std.testing.allocator;
    const r = try run(.{
        .allocator = a,
        .argv = &.{"/bin/pwd"},
    });
    defer a.free(r.stdout);
    defer a.free(r.stderr);
    try std.testing.expect(r.stdout.len > 1);
}

test "runIo accepts an explicit Io" {
    const a = std.testing.allocator;
    var threaded: std.Io.Threaded = .init(a, .{});
    defer threaded.deinit();

    const r = try runIo(threaded.io(), .{
        .allocator = a,
        .argv = &.{ "/bin/echo", "explicit" },
    });
    defer a.free(r.stdout);
    defer a.free(r.stderr);
    try std.testing.expectEqualStrings("explicit\n", r.stdout);
}
