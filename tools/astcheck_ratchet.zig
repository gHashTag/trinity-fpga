//! Fail when a NEW file starts failing `zig ast-check`.
//!
//!   zig build astcheck                                  # check against the baseline
//!   zig run tools/astcheck_ratchet.zig -lc -- --update   # rewrite the baseline
//!
//! Why a ratchet and not a clean bill of health: 94 files under src/ and
//! tools/ do not pass ast-check, carrying 272 errors between them. Demanding
//! zero would mean either a very long branch or a permanently red gate, and a
//! permanently red gate reads as a broken subject rather than a broken check --
//! the harder failure to notice. So this defends the number instead.
//!
//! What ast-check does and does not see, stated here so the figure never
//! travels without its caveat:
//!
//!   IT SEES     syntax, unused parameters and locals, shadowing, discards,
//!               undeclared identifiers, unreachable code
//!   IT DOES NOT resolve types or members. A struct literal missing a field,
//!               a call with the wrong arity, a misspelled member on an
//!               imported type -- all Sema, all invisible here. One such
//!               error in codegen/patterns/rl.zig made an entire subtree
//!               unimportable while every gate called it clean.
//!
//! So a green run here is not "the tree compiles". It is "no file got
//! syntactically worse".
//!
//! phi^2 + 1/phi^2 = 3 = TRINITY

const std = @import("std");
const tri_io = @import("tri_io");
const tri_proc = @import("tri_proc");

const baseline_path = "tools/astcheck_baseline.txt";
const roots = [_][]const u8{ "src", "tools" };

pub fn main(init: std.process.Init.Minimal) !void {
    var gpa_state: std.heap.DebugAllocator(.{}) = .init;
    defer _ = gpa_state.deinit();
    const gpa = gpa_state.allocator();
    const io = tri_io.get();

    var out_buf: [4096]u8 = undefined;
    var stdout = std.Io.File.stdout().writer(io, &out_buf);
    const out = &stdout.interface;
    defer out.flush() catch {};

    const args = try init.args.toSlice(gpa);
    defer gpa.free(args);
    var update = false;
    for (args[1..]) |a| {
        if (std.mem.eql(u8, a, "--update")) update = true;
    }

    // The instrument, before any counting. A census whose tool has not been
    // shown to reject a defect is a count of nothing -- this repository has
    // produced enough of those to make the check non-negotiable.
    try selfCheck(gpa, io, out);

    var files: std.ArrayList([]u8) = .empty;
    defer {
        for (files.items) |f| gpa.free(f);
        files.deinit(gpa);
    }
    for (roots) |root| try collectZig(gpa, io, root, &files);

    if (files.items.len == 0) {
        try out.print("no .zig files found under src/ or tools/ -- refusing to report over an empty set\n", .{});
        return error.EmptyDenominator;
    }
    std.mem.sort([]u8, files.items, {}, lessThanStr);

    var failing: std.ArrayList([]const u8) = .empty;
    defer failing.deinit(gpa);
    var errors: usize = 0;
    for (files.items) |f| {
        const n = astCheckErrors(gpa, io, f) catch continue;
        if (n > 0) {
            try failing.append(gpa, f);
            errors += n;
        }
    }

    if (update) {
        var file = try std.Io.Dir.cwd().createFile(io, baseline_path, .{});
        defer file.close(io);
        var wbuf: [8192]u8 = undefined;
        var w = file.writer(io, &wbuf);
        for (failing.items) |f| try w.interface.print("{s}\n", .{f});
        try w.interface.flush();
        try out.print("baseline written: {d} files rejected by ast-check ({d} errors)\n", .{ failing.items.len, errors });
        return;
    }

    const baseline = std.Io.Dir.cwd().readFileAlloc(io, baseline_path, gpa, .limited(4 * 1024 * 1024)) catch null;
    defer if (baseline) |b| gpa.free(b);
    if (baseline == null) {
        try out.print("no baseline yet -- run with --update to record one\n", .{});
        return error.NoBaseline;
    }

    var known = std.StringHashMap(void).init(gpa);
    defer known.deinit();
    var lines = std.mem.splitScalar(u8, baseline.?, '\n');
    while (lines.next()) |line| {
        const t = std.mem.trim(u8, line, " \t\r");
        if (t.len > 0) try known.put(t, {});
    }

    // The failure diagnostic goes to STDERR, not to `out`.
    //
    // `zig build` swallows a failing run step's stdout: the first negative
    // control of this gate exited 1 with the "NEW:" line nowhere in the
    // output, which is a gate that will not tell you what it caught. stderr
    // is forwarded on the failure path, so that is where the names belong.
    var fresh: usize = 0;
    for (failing.items) |f| {
        if (!known.contains(f)) {
            std.debug.print("  NEW: {s} fails ast-check and is not in the baseline\n", .{f});
            fresh += 1;
        }
    }

    if (fresh > 0) {
        std.debug.print(
            \\
            \\{d} file(s) newly fail ast-check.
            \\
            \\Fix them, or -- if the failure is genuinely pre-existing and you
            \\only moved the file -- re-record with:
            \\  zig build astcheck-update
            \\
        , .{fresh});
        return error.NewAstCheckFailures;
    }

    try out.print(
        \\no new ast-check failures ({d} known, {d} errors)
        \\  ast-check sees syntax and name binding, NOT types or members --
        \\  a green run here does not mean the tree compiles.
        \\
    , .{ failing.items.len, errors });
}

/// Prove ast-check rejects a known defect and accepts a clean file, or refuse
/// to report a number.
fn selfCheck(gpa: std.mem.Allocator, io: std.Io, out: *std.Io.Writer) !void {
    const bad_path = ".astcheck_probe_bad.zig";
    const good_path = ".astcheck_probe_good.zig";
    const cwd = std.Io.Dir.cwd();

    try cwd.writeFile(io, .{ .sub_path = bad_path, .data = "pub fn f(x: u8) void {}\n" });
    defer cwd.deleteFile(io, bad_path) catch {};
    try cwd.writeFile(io, .{ .sub_path = good_path, .data = "pub fn f(x: u8) u8 {\n    return x;\n}\n" });
    defer cwd.deleteFile(io, good_path) catch {};

    if (try astCheckErrors(gpa, io, bad_path) == 0) {
        try out.print("NEGATIVE CONTROL FAILED: ast-check accepted an unused parameter\n", .{});
        return error.InstrumentNotMeasuring;
    }
    if (try astCheckErrors(gpa, io, good_path) != 0) {
        try out.print("POSITIVE CONTROL FAILED: ast-check rejected a clean file\n", .{});
        return error.InstrumentTooStrict;
    }
}

fn astCheckErrors(gpa: std.mem.Allocator, io: std.Io, path: []const u8) !usize {
    const r = tri_proc.runIo(io, .{
        .allocator = gpa,
        .argv = &.{ "zig", "ast-check", path },
        .max_output_bytes = 1024 * 1024,
    }) catch return error.CouldNotRunAstCheck;
    defer gpa.free(r.stdout);
    defer gpa.free(r.stderr);

    var n: usize = 0;
    var it = std.mem.splitScalar(u8, r.stderr, '\n');
    while (it.next()) |line| {
        if (std.mem.indexOf(u8, line, ": error: ") != null) n += 1;
    }
    return n;
}

fn collectZig(gpa: std.mem.Allocator, io: std.Io, path: []const u8, acc: *std.ArrayList([]u8)) !void {
    var dir = std.Io.Dir.cwd().openDir(io, path, .{ .iterate = true }) catch return;
    defer dir.close(io);

    // 0.16: `iterate` takes no io, `next` does.
    var it = dir.iterate();
    while (try it.next(io)) |entry| {
        if (entry.name.len > 0 and entry.name[0] == '.') continue;
        if (std.mem.eql(u8, entry.name, "zig-out")) continue;

        const child = try std.fs.path.join(gpa, &.{ path, entry.name });
        switch (entry.kind) {
            .directory => {
                defer gpa.free(child);
                try collectZig(gpa, io, child, acc);
            },
            .file => {
                if (std.mem.endsWith(u8, entry.name, ".zig")) {
                    try acc.append(gpa, child);
                } else {
                    gpa.free(child);
                }
            },
            else => gpa.free(child),
        }
    }
}

fn lessThanStr(_: void, a: []u8, b: []u8) bool {
    return std.mem.order(u8, a, b) == .lt;
}

// ─── No two files may mutate the same literal /tmp path ────────────────────
//
// `zig build` runs independent test binaries in PARALLEL. Two files whose
// tests create and delete the same fixed path therefore race, and the loser
// fails with FileNotFound on a file it just wrote.
//
// That is not hypothetical: `shard_manager.zig` used a fixed
// `/tmp/trinity_test_5node` and deleteTree'd it on entry and exit -- 4
// failures in 20 runs, and it took three sessions to find because it only
// appears when two runs overlap. `src/libs/stdlib/impl/io.zig` and
// `tools/legacy/stdlib/impl/io.zig` are both declared test roots and were
// both writing `/tmp/vibee_io_test.txt`.
//
// A census found 51 tests mutating 56 distinct literal paths. Renaming the
// colliding ones fixes today; this test is what stops the next one, and it
// costs nothing to keep.

test "no literal /tmp path is mutated from more than one file" {
    const gpa = std.testing.allocator;
    const io = tri_io.get();

    var files: std.ArrayList([]u8) = .empty;
    defer {
        for (files.items) |f| gpa.free(f);
        files.deinit(gpa);
    }
    for (roots) |root| try collectZig(gpa, io, root, &files);
    // Guard the denominator: a walk that finds nothing would pass silently.
    try std.testing.expect(files.items.len > 500);

    // path -> first file that mutates it
    var owner = std.StringHashMap([]const u8).init(gpa);
    defer {
        var it = owner.keyIterator();
        while (it.next()) |k| gpa.free(k.*);
        owner.deinit();
    }

    var clashes: usize = 0;
    for (files.items) |path| {
        const src = std.Io.Dir.cwd().readFileAlloc(io, path, gpa, .limited(4 * 1024 * 1024)) catch continue;
        defer gpa.free(src);
        if (!mutatesAPath(src)) continue;

        // Only paths written INSIDE a test block count. The first version of
        // this check scanned whole files and flagged `/tmp/.tri_cache.json`,
        // which is a production cache default that happens to appear in two
        // duplicated source files -- a real duplication, but not a test
        // collision, and not something this test should be the one to fail
        // over.
        var i: usize = 0;
        while (std.mem.indexOfPos(u8, src, i, "\"/tmp/")) |at| {
            if (!insideTestBlock(src, at)) {
                i = at + 1;
                continue;
            }
            const start = at + 1;
            const end = std.mem.indexOfScalarPos(u8, src, start, '"') orelse break;
            const lit = src[start..end];
            i = end + 1;
            if (lit.len <= "/tmp/".len) continue;

            if (owner.get(lit)) |first| {
                if (!std.mem.eql(u8, first, path)) {
                    std.debug.print(
                        "  {s} is mutated from two files:\n    {s}\n    {s}\n",
                        .{ lit, first, path },
                    );
                    clashes += 1;
                }
            } else {
                const key = try gpa.dupe(u8, lit);
                try owner.put(key, path);
            }
        }
    }

    try std.testing.expectEqual(@as(usize, 0), clashes);
}

/// Is byte `at` inside a `test "..." { ... }` block?
///
/// Counted by brace depth from the nearest preceding `\ntest "`, so a path in
/// a helper function below the test does not get mistaken for one in it.
fn insideTestBlock(src: []const u8, at: usize) bool {
    const head = src[0..at];
    const test_at = std.mem.lastIndexOf(u8, head, "\ntest \"") orelse return false;
    const open = std.mem.indexOfScalarPos(u8, src, test_at, '{') orelse return false;
    if (open > at) return false;
    var depth: usize = 0;
    var i = open;
    while (i < at) : (i += 1) {
        if (src[i] == '{') depth += 1;
        if (src[i] == '}') {
            if (depth == 0) return false;
            depth -= 1;
        }
    }
    return depth > 0;
}

fn mutatesAPath(src: []const u8) bool {
    const mutators = [_][]const u8{
        "deleteTree", "deleteDir",  "deleteFile", "createDirPath",
        "makePath",   "createFile", "writeFile",  "makeDir",
    };
    for (mutators) |m| {
        if (std.mem.indexOf(u8, src, m) != null) return true;
    }
    return false;
}
