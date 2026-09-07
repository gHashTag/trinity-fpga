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
const tri_env = @import("tri_env");

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

/// PATH resolution, which 0.16 made the caller's job.
///
/// THIS IS A BEHAVIOUR CHANGE, not a rename, and it is invisible at compile
/// time. 0.15's `Child.spawn` ultimately called execvpe, which searches PATH,
/// so `argv[0] = "zig"` worked. Both `std.process.spawn` and
/// `std.process.run` in 0.16 require a path they can open, and answer a bare
/// name with error.FileNotFound. `expand_arg0 = .expand` does NOT restore it
/// (verified against 0.16.0).
///
/// Every subprocess call in this tree names its program bare -- "zig", "gh",
/// "git", "sh" -- so without this, all of them fail at runtime while
/// compiling perfectly. `tri fmt` was the one that surfaced it.
///
/// Returns an allocated absolute path, or null when the name is not found.
/// A name that already contains '/' is returned as-is: it is a path already,
/// and PATH lookup would be wrong.
pub fn resolveProgram(gpa: std.mem.Allocator, name: []const u8) !?[]u8 {
    if (std.mem.indexOfScalar(u8, name, '/') != null) return try gpa.dupe(u8, name);

    const path_env = tri_env.getPosix("PATH") orelse return null;
    var it = std.mem.splitScalar(u8, path_env, ':');
    while (it.next()) |dir| {
        if (dir.len == 0) continue;
        const candidate = try std.fs.path.join(gpa, &.{ dir, name });
        errdefer gpa.free(candidate);
        // X_OK is not expressible through Io.Dir.access, so ask libc directly.
        const cz = try gpa.dupeZ(u8, candidate);
        defer gpa.free(cz);
        if (c_access.access(cz.ptr, 1) == 0) return candidate; // 1 == X_OK
        gpa.free(candidate);
    }
    return null;
}

const c_access = struct {
    extern "c" fn access(path: [*:0]const u8, mode: c_int) c_int;
};

/// Copies `argv` with argv[0] replaced by its resolved absolute path.
/// Caller frees the returned slice and its first element.
fn resolvedArgv(gpa: std.mem.Allocator, argv: []const []const u8) !?[][]const u8 {
    if (argv.len == 0) return null;
    const full = (try resolveProgram(gpa, argv[0])) orelse return null;
    errdefer gpa.free(full);
    const out = try gpa.alloc([]const u8, argv.len);
    out[0] = full;
    for (argv[1..], 1..) |a, i| out[i] = a;
    return out;
}

/// PATH-resolving wrapper over `std.process.spawn`, for the call sites that
/// spawn and wait separately rather than using `run`. Same reason as
/// `resolveProgram`: a bare argv[0] is error.FileNotFound in 0.16.
///
/// The caller owns the returned Child and must `wait` it.
/// Takes no allocator on purpose. Several call sites have none in scope, and
/// the only allocation here is a short-lived path that is freed before this
/// function returns, so the page allocator is the right size of hammer.
pub fn spawn(io: std.Io, options: std.process.SpawnOptions) !std.process.Child {
    const gpa = std.heap.page_allocator;
    const resolved = resolvedArgv(gpa, options.argv) catch null;
    defer if (resolved) |r| {
        gpa.free(r[0]);
        gpa.free(r);
    };
    var opts = options;
    if (resolved) |r| opts.argv = r;
    return std.process.spawn(io, opts);
}

/// Drop-in for the removed `std.process.Child.run`.
pub fn run(options: RunOptions) RunError!RunResult {
    return runIo(tri_io.get(), options);
}

/// Same, but with an explicit Io. Prefer this wherever one is already in
/// scope -- reaching for the ambient handle when a parameter is available
/// defeats the point of the migration.
pub fn runIo(io: std.Io, options: RunOptions) RunError!RunResult {
    // Resolve argv[0] through PATH; see resolveProgram. If it cannot be
    // found, fall through with the original argv so the caller still gets
    // error.FileNotFound rather than a different, more confusing failure.
    const resolved = resolvedArgv(options.allocator, options.argv) catch null;
    defer if (resolved) |r| {
        options.allocator.free(r[0]);
        options.allocator.free(r);
    };
    const argv = if (resolved) |r| r else options.argv;

    return std.process.run(options.allocator, io, .{
        .argv = argv,
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

test "resolveProgram finds a bare program name on PATH" {
    const gpa = std.testing.allocator;
    // This is the regression that "it compiles" hid: 0.15 resolved a bare
    // name through PATH and 0.16 does not, so this test is the guard.
    const p = (try resolveProgram(gpa, "sh")).?;
    defer gpa.free(p);
    try std.testing.expect(std.mem.endsWith(u8, p, "/sh"));
    try std.testing.expect(p[0] == '/');
}

test "resolveProgram passes an explicit path straight through" {
    const gpa = std.testing.allocator;
    const p = (try resolveProgram(gpa, "/bin/sh")).?;
    defer gpa.free(p);
    try std.testing.expectEqualStrings("/bin/sh", p);
}

test "resolveProgram returns null for a name that is not on PATH" {
    const gpa = std.testing.allocator;
    try std.testing.expect(try resolveProgram(gpa, "definitely-not-a-real-program-xyz") == null);
}

test "run executes a bare program name" {
    const gpa = std.testing.allocator;
    // The end-to-end proof: before PATH resolution this returned
    // error.FileNotFound for every call site in the tree.
    const res = try run(.{ .allocator = gpa, .argv = &.{ "sh", "-c", "printf trinity" } });
    defer gpa.free(res.stdout);
    defer gpa.free(res.stderr);
    try std.testing.expectEqualStrings("trinity", res.stdout);
    try std.testing.expectEqual(@as(u8, 0), res.term.exited);
}
