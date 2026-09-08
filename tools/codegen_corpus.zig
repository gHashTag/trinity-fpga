//! Generate every .tri/.vibee spec and check the output, as a ratchet.
//!
//!   zig build codegen-corpus              # check against the baseline
//!   zig build codegen-corpus-update       # re-record the baseline
//!
//! Why this exists: the CI gate compiled FOUR specs, and my own sweeps used an
//! arbitrary `head -80` of the tree. The real population is 1137 specs, 1033 of
//! which produce behaviours. Every corpus figure quoted during the generator
//! work -- "24 of 49", "34 of 49" -- came from a ~5% slice, and a regression
//! reached a commit because the failing spec was not in it.
//!
//! Two instruments, deliberately:
//!
//!   ast-check   every spec with behaviours. Fast (about a minute), and it
//!               catches syntax and name-binding regressions across the whole
//!               corpus. This is what the ratchet defends.
//!   compile     `zig test` on a sample, because it is ~3s per spec and the
//!               full set would take 40 minutes. It sees what ast-check cannot
//!               -- call arity, types, members -- which is exactly the class
//!               that slipped through before.
//!
//! phi^2 + 1/phi^2 = 3 = TRINITY

const std = @import("std");
const tri_io = @import("tri_io");
const tri_proc = @import("tri_proc");

const baseline_path = "tools/codegen_corpus_baseline.txt";
const out_dir = ".zig-cache/codegen-corpus";
/// Default number of clean specs to additionally COMPILE. Compiling is ~3s
/// each, so every-push runs stay near a minute; `--compile N` raises it for a
/// nightly. `--compile all` takes about 40 minutes.
///
/// The sample is not the first N: it is spread evenly across the corpus.
/// `ternary_mathematics` failed the four-spec gate through five iterations of
/// a change while a contiguous 24-spec prefix said everything was clean --
/// a prefix samples one directory, not the corpus.
const default_compile_sample = 24;

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
    var gen_arg: ?[]const u8 = null;
    var compile_sample: usize = default_compile_sample;
    var want_compile_arg = false;
    for (args[1..]) |a| {
        if (want_compile_arg) {
            want_compile_arg = false;
            if (std.mem.eql(u8, a, "all")) {
                compile_sample = std.math.maxInt(usize);
            } else {
                compile_sample = std.fmt.parseInt(usize, a, 10) catch default_compile_sample;
            }
        } else if (std.mem.eql(u8, a, "--update")) {
            update = true;
        } else if (std.mem.eql(u8, a, "--compile")) {
            want_compile_arg = true;
        } else if (gen_arg == null) {
            gen_arg = a;
        }
    }

    // The build passes the generator's path as an argument
    // (`addArtifactArg`), which both locates it and makes this step depend on
    // it being built. Searching `.zig-cache` was the first approach and it
    // worked only on a machine that had already built the generator: CI runs
    // this step without building `vibee_gen`, so it failed with
    // `GeneratorNotBuilt` -- a gate that passed locally and could not pass
    // anywhere else.
    const gen = if (gen_arg) |g| try gpa.dupe(u8, g) else try findGenerator(gpa, io);
    defer gpa.free(gen);

    std.Io.Dir.cwd().createDirPath(io, out_dir) catch {};

    var specs: std.ArrayList([]u8) = .empty;
    defer {
        for (specs.items) |s| gpa.free(s);
        specs.deinit(gpa);
    }
    try collectSpecs(gpa, io, "specs", &specs);
    if (specs.items.len == 0) {
        try out.print("no specs found -- refusing to report over an empty set\n", .{});
        return error.EmptyDenominator;
    }
    std.mem.sort([]u8, specs.items, {}, lessThanStr);

    var clean: std.ArrayList([]const u8) = .empty;
    defer clean.deinit(gpa);
    var with_behaviours: usize = 0;
    var dirty: usize = 0;

    for (specs.items) |spec| {
        const dest = try outPathFor(gpa, spec);
        defer gpa.free(dest);

        const behaviours = try generate(gpa, io, gen, spec, dest);
        if (behaviours == 0) continue;
        with_behaviours += 1;

        if (try astCheckOk(gpa, io, dest)) {
            try clean.append(gpa, spec);
        } else {
            dirty += 1;
        }
    }

    if (update) {
        var file = try std.Io.Dir.cwd().createFile(io, baseline_path, .{});
        defer file.close(io);
        var wbuf: [8192]u8 = undefined;
        var w = file.writer(io, &wbuf);
        for (clean.items) |s| try w.interface.print("{s}\n", .{s});
        try w.interface.flush();
        try out.print(
            "baseline written: {d} of {d} specs with behaviours generate ast-check-clean output\n",
            .{ clean.items.len, with_behaviours },
        );
        return;
    }

    const baseline = std.Io.Dir.cwd().readFileAlloc(io, baseline_path, gpa, .limited(4 * 1024 * 1024)) catch null;
    defer if (baseline) |b| gpa.free(b);
    if (baseline == null) {
        try out.print("no baseline yet -- run `zig build codegen-corpus-update`\n", .{});
        return error.NoBaseline;
    }

    var now = std.StringHashMap(void).init(gpa);
    defer now.deinit();
    for (clean.items) |s| try now.put(s, {});

    // A spec whose output USED to be clean and now is not. Regressions only --
    // a spec that was already failing is not this gate's business.
    var regressed: usize = 0;
    var lines = std.mem.splitScalar(u8, baseline.?, '\n');
    while (lines.next()) |line| {
        const t = std.mem.trim(u8, line, " \t\r");
        if (t.len == 0) continue;
        if (!now.contains(t)) {
            std.debug.print("  REGRESSED: {s} no longer generates ast-check-clean output\n", .{t});
            regressed += 1;
        }
    }

    // The compile sample: what ast-check cannot see. Arity, types, members.
    var compiled: usize = 0;
    var compile_failed: usize = 0;
    const sample = @min(compile_sample, clean.items.len);
    // Even stride, not a prefix: the clean list is sorted by path, so the
    // first N are all from one directory.
    const stride = if (sample == 0) 1 else clean.items.len / sample;
    var picked: std.ArrayList([]const u8) = .empty;
    defer picked.deinit(gpa);
    {
        var i: usize = 0;
        while (i < clean.items.len and picked.items.len < sample) : (i += @max(1, stride)) {
            try picked.append(gpa, clean.items[i]);
        }
    }
    for (picked.items) |spec| {
        const dest = try outPathFor(gpa, spec);
        defer gpa.free(dest);
        if (try zigTestOk(gpa, io, dest)) {
            compiled += 1;
        } else {
            std.debug.print("  DOES NOT COMPILE: {s} (ast-check passed it)\n", .{spec});
            compile_failed += 1;
        }
    }

    if (regressed > 0 or compile_failed > 0) {
        std.debug.print(
            \\
            \\{d} spec(s) regressed, {d} of {d} sampled outputs do not compile.
            \\
            \\Re-record only if the change is intended:
            \\  zig build codegen-corpus-update
            \\
        , .{ regressed, compile_failed, sample });
        return error.CodegenCorpusRegressed;
    }

    try out.print(
        \\codegen corpus: {d} of {d} specs with behaviours generate clean output
        \\  no regressions against the baseline
        \\  {d} of those additionally COMPILED (zig test) -- ast-check alone
        \\  cannot see call arity, types or members
        \\
    , .{ clean.items.len, with_behaviours, compiled });
}

fn findGenerator(gpa: std.mem.Allocator, io: std.Io) ![]u8 {
    // The build places it under .zig-cache/o/<hash>/vibee_gen; take the newest.
    const r = try tri_proc.runIo(io, .{
        .allocator = gpa,
        .argv = &.{ "sh", "-c", "find .zig-cache -name vibee_gen -type f -perm +111 -exec ls -t {} + 2>/dev/null | head -1" },
        .max_output_bytes = 4096,
    });
    defer gpa.free(r.stderr);
    errdefer gpa.free(r.stdout);
    const path = std.mem.trim(u8, r.stdout, " \n\r\t");
    if (path.len == 0) {
        gpa.free(r.stdout);
        return error.GeneratorNotBuilt;
    }
    const owned = try gpa.dupe(u8, path);
    gpa.free(r.stdout);
    return owned;
}

fn outPathFor(gpa: std.mem.Allocator, spec: []const u8) ![]u8 {
    const flat = try gpa.dupe(u8, spec);
    defer gpa.free(flat);
    for (flat) |*c| {
        if (c.* == '/') c.* = '_';
    }
    return std.fmt.allocPrint(gpa, "{s}/{s}.zig", .{ out_dir, flat });
}

/// Returns the behaviour count the generator reports, or 0.
fn generate(gpa: std.mem.Allocator, io: std.Io, gen: []const u8, spec: []const u8, dest: []const u8) !usize {
    const r = tri_proc.runIo(io, .{
        .allocator = gpa,
        .argv = &.{ gen, "gen", spec, dest },
        .max_output_bytes = 256 * 1024,
    }) catch return 0;
    defer gpa.free(r.stdout);
    defer gpa.free(r.stderr);

    const needle = "Behaviors: ";
    const hay = if (std.mem.indexOf(u8, r.stderr, needle) != null) r.stderr else r.stdout;
    const at = std.mem.indexOf(u8, hay, needle) orelse return 0;
    var i = at + needle.len;
    var n: usize = 0;
    while (i < hay.len and std.ascii.isDigit(hay[i])) : (i += 1) {
        n = n * 10 + (hay[i] - '0');
    }
    return n;
}

fn astCheckOk(gpa: std.mem.Allocator, io: std.Io, path: []const u8) !bool {
    const r = tri_proc.runIo(io, .{
        .allocator = gpa,
        .argv = &.{ "zig", "ast-check", path },
        .max_output_bytes = 256 * 1024,
    }) catch return false;
    defer gpa.free(r.stdout);
    defer gpa.free(r.stderr);
    return std.mem.indexOf(u8, r.stderr, ": error: ") == null;
}

fn zigTestOk(gpa: std.mem.Allocator, io: std.Io, path: []const u8) !bool {
    const r = tri_proc.runIo(io, .{
        .allocator = gpa,
        // A SEPARATE cache dir. This tool runs inside `zig build`, which
        // holds a lock on `.zig-cache`; a child `zig test` using the same
        // directory fails, and `catch return false` reported that as "does
        // not compile". It said 24 of 24 sampled outputs were broken when
        // every one of them compiles and passes by hand.
        // Both cache dirs are passed explicitly.
        //
        // --cache-dir: this tool runs inside `zig build`, which holds a lock
        //   on `.zig-cache`.
        // --global-cache-dir: the child inherits no environment through
        //   tri_proc, so `zig` cannot resolve HOME and fails with
        //   `AppDataDirUnavailable`. That error was invisible behind
        //   `catch return false`, which reported it as "does not compile" for
        //   24 of 24 sampled specs -- every one of which compiles by hand.
        .argv = &.{
            "zig",                "test",
            "--cache-dir",        ".zig-cache/corpus-child",
            "--global-cache-dir", ".zig-cache/corpus-global",
            path,
        },
        .max_output_bytes = 512 * 1024,
    }) catch return false;
    defer gpa.free(r.stdout);
    defer gpa.free(r.stderr);
    return switch (r.term) {
        .exited => |c| c == 0,
        else => false,
    };
}

fn collectSpecs(gpa: std.mem.Allocator, io: std.Io, path: []const u8, acc: *std.ArrayList([]u8)) !void {
    var dir = std.Io.Dir.cwd().openDir(io, path, .{ .iterate = true }) catch return;
    defer dir.close(io);

    var it = dir.iterate();
    while (try it.next(io)) |entry| {
        if (entry.name.len > 0 and entry.name[0] == '.') continue;
        const child = try std.fs.path.join(gpa, &.{ path, entry.name });
        switch (entry.kind) {
            .directory => {
                defer gpa.free(child);
                try collectSpecs(gpa, io, child, acc);
            },
            .file => {
                if (std.mem.endsWith(u8, entry.name, ".tri") or
                    std.mem.endsWith(u8, entry.name, ".vibee"))
                {
                    try acc.append(gpa, child);
                } else gpa.free(child);
            },
            else => gpa.free(child),
        }
    }
}

fn lessThanStr(_: void, a: []u8, b: []u8) bool {
    return std.mem.order(u8, a, b) == .lt;
}
