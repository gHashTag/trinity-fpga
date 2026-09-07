//! How many files carry tests that nothing runs?
//!
//!   zig run tools/test_coverage.zig -lc                  # report
//!   zig run tools/test_coverage.zig -lc -- --update      # rewrite the baseline
//!
//! WHY THIS EXISTS. Adding tests to four files during the 0.16 migration, a
//! probe -- an always-failing test appended to each -- showed that only ONE of
//! them ran under `zig build test`. The token-permission tests and the
//! PATH-resolution tests, both of which had already caught real defects, were
//! decoration. `zig build test` declares a fixed list of roots; a test in a
//! file outside that list is never compiled, never run, and never reported.
//!
//! Measured across the tree afterwards: 1689 files under src/ contain tests
//! and roughly 150 are reachable. A test nothing runs is the same defect as a
//! gate that cannot fail, one level up -- and it is worse, because a written
//! test looks like coverage in every review.
//!
//! WHAT THIS IS NOT. It is not a demand that all 1689 be wired up. Many are
//! dead files, generated fixtures, or modules that cannot compile standalone.
//! It is a RATCHET: the count is recorded, and it must not grow. New tests
//! land in files that run, or the number is deliberately raised with a reason.
//!
//! LIMITATION, printed in the output as well as here: reachability follows
//! `@import("path.zig")` and `@import("module_name")` resolved through
//! build.zig. It cannot see a root added by a helper function or a loop over a
//! non-literal, so the orphan count is an UPPER bound. Spot-check a surprising
//! entry with the probe before acting on it:
//!
//!     printf '\ntest "PROBE" { try @import("std").testing.expect(false); }\n' >> FILE
//!     zig build test    # rc=0 means the file does not run
//!
//! phi^2 + 1/phi^2 = 3 = TRINITY

const std = @import("std");

const baseline_path = "tools/test_coverage_baseline.txt";

pub fn main(init: std.process.Init.Minimal) !void {
    var gpa_state: std.heap.DebugAllocator(.{}) = .init;
    defer _ = gpa_state.deinit();
    const gpa = gpa_state.allocator();

    var threaded: std.Io.Threaded = .init(gpa, .{});
    defer threaded.deinit();
    const io = threaded.io();

    const args = try init.args.toSlice(gpa);
    defer gpa.free(args);
    var update = false;
    for (args) |a| {
        if (std.mem.eql(u8, a, "--update")) update = true;
    }

    const build_src = try std.Io.Dir.cwd().readFileAlloc(io, "build.zig", gpa, .limited(4 * 1024 * 1024));
    defer gpa.free(build_src);

    var modules = try parseModules(gpa, build_src);
    defer {
        var it = modules.iterator();
        while (it.next()) |e| {
            gpa.free(e.key_ptr.*);
            gpa.free(e.value_ptr.*);
        }
        modules.deinit();
    }

    var reachable = try reachableFromTestRoots(gpa, io, build_src, &modules);
    defer {
        var it = reachable.keyIterator();
        while (it.next()) |k| gpa.free(k.*);
        reachable.deinit();
    }

    var orphans: std.ArrayList([]const u8) = .empty;
    defer {
        for (orphans.items) |o| gpa.free(o);
        orphans.deinit(gpa);
    }
    var with_tests: usize = 0;
    try collectOrphans(gpa, io, "src", &reachable, &orphans, &with_tests);

    std.mem.sort([]const u8, orphans.items, {}, lessThanStr);

    var out_buf: [4096]u8 = undefined;
    var w = std.Io.File.stdout().writerStreaming(io, &out_buf);
    const out = &w.interface;

    if (update) {
        var aw: std.Io.Writer.Allocating = .init(gpa);
        defer aw.deinit();
        for (orphans.items) |o| try aw.writer.print("{s}\n", .{o});
        var f = try std.Io.Dir.cwd().createFile(io, baseline_path, .{});
        defer f.close(io);
        try f.writeStreamingAll(io, aw.written());
        try out.print("baseline written: {d} files with tests that nothing runs\n", .{orphans.items.len});
        try out.flush();
        return;
    }

    try out.print("files under src/ containing tests : {d}\n", .{with_tests});
    try out.print("reachable from the `test` step    : {d}\n", .{with_tests - orphans.items.len});
    try out.print("NOT reachable -- tests nothing runs: {d}\n\n", .{orphans.items.len});

    const baseline = std.Io.Dir.cwd().readFileAlloc(io, baseline_path, gpa, .limited(4 * 1024 * 1024)) catch null;
    defer if (baseline) |b| gpa.free(b);

    if (baseline == null) {
        try out.print("no baseline yet -- run with --update to record one\n", .{});
        try out.flush();
        return;
    }

    var known: std.StringHashMap(void) = .init(gpa);
    defer known.deinit();
    var lines = std.mem.splitScalar(u8, baseline.?, '\n');
    while (lines.next()) |l| {
        const t = std.mem.trim(u8, l, " \r\n");
        if (t.len > 0) try known.put(t, {});
    }

    var added: usize = 0;
    for (orphans.items) |o| {
        if (!known.contains(o)) {
            if (added == 0) try out.print("NEW files whose tests nothing runs:\n", .{});
            try out.print("  {s}\n", .{o});
            added += 1;
        }
    }

    try out.print("\nreachability follows @import(\"path.zig\") and @import(\"module\") via\n", .{});
    try out.print("build.zig. A root added by a helper or a non-literal loop is invisible,\n", .{});
    try out.print("so this count is an UPPER bound. Probe before acting on a surprise.\n", .{});

    if (added > 0) {
        try out.print("\n{d} file(s) gained tests that nothing will run.\n", .{added});
        try out.print("Wire the file into the `test` step, or record it with --update and say why.\n", .{});
        try out.flush();
        return error.NewUnrunTests;
    }
    try out.print("\nno new unrun tests ({d} known)\n", .{known.count()});
    try out.flush();
}

fn lessThanStr(_: void, a: []const u8, b: []const u8) bool {
    return std.mem.lessThan(u8, a, b);
}

/// module name -> root source path, from build.zig.
fn parseModules(gpa: std.mem.Allocator, src: []const u8) !std.StringHashMap([]const u8) {
    var vars: std.StringHashMap([]const u8) = .init(gpa);
    defer {
        var it = vars.iterator();
        while (it.next()) |e| {
            gpa.free(e.key_ptr.*);
            gpa.free(e.value_ptr.*);
        }
        vars.deinit();
    }

    var i: usize = 0;
    while (std.mem.indexOfPos(u8, src, i, "= b.createModule(")) |at| {
        var e = at;
        while (e > 0 and src[e - 1] == ' ') e -= 1;
        var b0 = e;
        while (b0 > 0 and (std.ascii.isAlphanumeric(src[b0 - 1]) or src[b0 - 1] == '_')) b0 -= 1;
        const vname = src[b0..e];

        const key = "root_source_file = b.path(\"";
        const kat = std.mem.indexOfPos(u8, src, at, key) orelse break;
        const ps = kat + key.len;
        const pe = std.mem.indexOfPos(u8, src, ps, "\"") orelse break;
        if (vname.len > 0) {
            const g = try vars.getOrPut(vname);
            if (g.found_existing) gpa.free(g.value_ptr.*) else g.key_ptr.* = try gpa.dupe(u8, vname);
            g.value_ptr.* = try gpa.dupe(u8, src[ps..pe]);
        }
        i = pe;
    }

    var names: std.StringHashMap([]const u8) = .init(gpa);
    i = 0;
    while (std.mem.indexOfPos(u8, src, i, ".name = \"")) |at| {
        const ns = at + ".name = \"".len;
        const ne = std.mem.indexOfPos(u8, src, ns, "\"") orelse break;
        const name = src[ns..ne];
        i = ne + 1;

        const mk = ".module = ";
        const mat = std.mem.indexOfPos(u8, src, ne, mk) orelse continue;
        if (mat > ne + 40) continue;
        var vs = mat + mk.len;
        var ve = vs;
        while (ve < src.len and (std.ascii.isAlphanumeric(src[ve]) or src[ve] == '_')) ve += 1;
        if (vars.get(src[vs..ve])) |path| {
            if (!names.contains(name)) try names.put(try gpa.dupe(u8, name), try gpa.dupe(u8, path));
        }
        vs = 0;
    }
    return names;
}

/// Every file the `test` step can compile: the addTest roots plus their
/// transitive imports.
fn reachableFromTestRoots(
    gpa: std.mem.Allocator,
    io: std.Io,
    build_src: []const u8,
    modules: *const std.StringHashMap([]const u8),
) !std.StringHashMap(void) {
    var set: std.StringHashMap(void) = .init(gpa);
    var queue: std.ArrayList([]const u8) = .empty;
    defer {
        for (queue.items) |q| gpa.free(q);
        queue.deinit(gpa);
    }

    // Roots: every b.path("...") that appears inside an addTest block, plus the
    // explicit behaviour-test list.
    var i: usize = 0;
    while (std.mem.indexOfPos(u8, build_src, i, "b.addTest(")) |at| {
        const window_end = @min(build_src.len, at + 2000);
        const window = build_src[at..window_end];
        if (std.mem.indexOf(u8, window, "b.path(\"")) |rel| {
            const ps = at + rel + "b.path(\"".len;
            const pe = std.mem.indexOfPos(u8, build_src, ps, "\"") orelse break;
            try queue.append(gpa, try gpa.dupe(u8, build_src[ps..pe]));
        }
        i = at + 1;
    }
    if (std.mem.indexOf(u8, build_src, "behaviour_test_roots = ")) |bt| {
        const stop = std.mem.indexOfPos(u8, build_src, bt, "};") orelse build_src.len;
        var j = bt;
        while (std.mem.indexOfPos(u8, build_src[0..stop], j, "b.path(\"")) |at| {
            const ps = at + "b.path(\"".len;
            const pe = std.mem.indexOfPos(u8, build_src, ps, "\"") orelse break;
            try queue.append(gpa, try gpa.dupe(u8, build_src[ps..pe]));
            j = pe;
        }
    }

    var head: usize = 0;
    while (head < queue.items.len) : (head += 1) {
        const cur = queue.items[head];
        const norm = try normalize(gpa, cur);
        if (set.contains(norm)) {
            gpa.free(norm);
            continue;
        }
        try set.put(norm, {});

        const body = std.Io.Dir.cwd().readFileAlloc(io, norm, gpa, .limited(8 * 1024 * 1024)) catch continue;
        defer gpa.free(body);
        const dir = std.fs.path.dirname(norm) orelse ".";

        var k: usize = 0;
        while (std.mem.indexOfPos(u8, body, k, "@import(\"")) |at| {
            const ns = at + "@import(\"".len;
            const ne = std.mem.indexOfPos(u8, body, ns, "\"") orelse break;
            const name = body[ns..ne];
            k = ne + 1;

            var target: []const u8 = undefined;
            var owned = false;
            if (std.mem.endsWith(u8, name, ".zig")) {
                target = try std.fs.path.join(gpa, &.{ dir, name });
                owned = true;
            } else if (modules.get(name)) |m| {
                target = m;
            } else continue;
            defer if (owned) gpa.free(target);

            std.Io.Dir.cwd().access(io, target, .{}) catch continue;
            try queue.append(gpa, try gpa.dupe(u8, target));
        }
    }
    return set;
}

fn collectOrphans(
    gpa: std.mem.Allocator,
    io: std.Io,
    dir_path: []const u8,
    reachable: *const std.StringHashMap(void),
    orphans: *std.ArrayList([]const u8),
    with_tests: *usize,
) !void {
    var dir = std.Io.Dir.cwd().openDir(io, dir_path, .{ .iterate = true }) catch return;
    defer dir.close(io);

    var it = dir.iterate();
    while (try it.next(io)) |entry| {
        if (entry.name.len > 0 and entry.name[0] == '.') continue;
        const child = try std.fmt.allocPrint(gpa, "{s}/{s}", .{ dir_path, entry.name });
        defer gpa.free(child);

        if (entry.kind == .directory) {
            try collectOrphans(gpa, io, child, reachable, orphans, with_tests);
            continue;
        }
        if (entry.kind != .file or !std.mem.endsWith(u8, entry.name, ".zig")) continue;

        const body = std.Io.Dir.cwd().readFileAlloc(io, child, gpa, .limited(16 * 1024 * 1024)) catch continue;
        defer gpa.free(body);
        if (!hasTest(body)) continue;
        with_tests.* += 1;
        if (!reachable.contains(child)) try orphans.append(gpa, try gpa.dupe(u8, child));
    }
}

/// A `test` declaration at column zero. Anchored so the word inside a comment
/// or a string does not count -- the mistake that has produced wrong counts
/// elsewhere in this tree.
fn hasTest(body: []const u8) bool {
    if (std.mem.startsWith(u8, body, "test ") or std.mem.startsWith(u8, body, "test{")) return true;
    var i: usize = 0;
    while (std.mem.indexOfPos(u8, body, i, "\ntest")) |at| {
        const after = at + "\ntest".len;
        if (after < body.len and (body[after] == ' ' or body[after] == '{' or body[after] == '"')) return true;
        i = at + 1;
    }
    return false;
}

fn normalize(gpa: std.mem.Allocator, path: []const u8) ![]u8 {
    var parts: std.ArrayList([]const u8) = .empty;
    defer parts.deinit(gpa);
    var it = std.mem.splitScalar(u8, path, '/');
    while (it.next()) |seg| {
        if (seg.len == 0 or std.mem.eql(u8, seg, ".")) continue;
        if (std.mem.eql(u8, seg, "..")) {
            if (parts.items.len > 0) _ = parts.pop();
            continue;
        }
        try parts.append(gpa, seg);
    }
    return std.mem.join(gpa, "/", parts.items);
}
