//! Counts remaining Zig 0.15-era API call sites, resolving namespace aliases.
//!
//! Run it:  zig run tools/api_census.zig -lc
//!
//! WHY THIS EXISTS. Every count published for the 0.16 migration before this
//! tool was a lower bound, because the patterns were spelled `std.fs.` and
//! `std.time.` while 21 files open with `const fs = std.fs;` or
//! `const time = std.time;` and then never write the prefix again.
//! `token_rotator.zig` read as fully migrated while holding eight untouched
//! `fs.cwd()` calls; it surfaced only when the compiler reached it.
//!
//! So this counts BOTH spellings: for each file it first collects the local
//! aliases of the std namespaces it cares about, then counts `std.fs.cwd(`
//! and `<alias>.cwd(` alike.
//!
//! It deliberately does NOT count matches inside line comments or string
//! literals. Both have burned this migration: a blanket replace corrupted a
//! shim's own `@hasDecl` guard comment, and four code generators emit Zig as
//! string literals, where a "call site" is data rather than code.
//!
//! phi^2 + 1/phi^2 = 3 = TRINITY

const std = @import("std");

/// A removed-or-changed API, named by the member accessed on a std namespace.
const Axis = struct {
    /// The std namespace this member lives on, e.g. "fs" in `std.fs.cwd`.
    namespace: []const u8,
    /// The member text that follows, e.g. "cwd(".
    member: []const u8,
    /// Short label for the report.
    label: []const u8,
};

const axes = [_]Axis{
    .{ .namespace = "fs", .member = "cwd(", .label = "fs.cwd(" },
    .{ .namespace = "fs", .member = "File", .label = "fs.File" },
    .{ .namespace = "fs", .member = "Dir", .label = "fs.Dir" },
    .{ .namespace = "fs", .member = "createFileAbsolute", .label = "fs.createFileAbsolute" },
    .{ .namespace = "fs", .member = "openFileAbsolute", .label = "fs.openFileAbsolute" },
    .{ .namespace = "time", .member = "timestamp(", .label = "time.timestamp(" },
    .{ .namespace = "time", .member = "milliTimestamp(", .label = "time.milliTimestamp(" },
    .{ .namespace = "time", .member = "nanoTimestamp(", .label = "time.nanoTimestamp(" },
    .{ .namespace = "time", .member = "Timer", .label = "time.Timer" },
    .{ .namespace = "process", .member = "Child.init(", .label = "process.Child.init(" },
    .{ .namespace = "process", .member = "Child.run(", .label = "process.Child.run(" },
    .{ .namespace = "process", .member = "argsAlloc", .label = "process.argsAlloc" },
    .{ .namespace = "process", .member = "getEnvVarOwned", .label = "process.getEnvVarOwned" },
    .{ .namespace = "process", .member = "getEnvMap", .label = "process.getEnvMap" },
    .{ .namespace = "posix", .member = "getenv(", .label = "posix.getenv(" },
    .{ .namespace = "io", .member = "fixedBufferStream", .label = "io.fixedBufferStream" },
    .{ .namespace = "Thread", .member = "Mutex", .label = "Thread.Mutex" },
    .{ .namespace = "Thread", .member = "RwLock", .label = "Thread.RwLock" },
    .{ .namespace = "Thread", .member = "Pool", .label = "Thread.Pool" },
    .{ .namespace = "Thread", .member = "sleep(", .label = "Thread.sleep(" },
    .{ .namespace = "crypto", .member = "random.", .label = "crypto.random." },
    .{ .namespace = "net", .member = "Address", .label = "net.Address" },
    .{ .namespace = "net", .member = "Stream", .label = "net.Stream" },
    .{ .namespace = "net", .member = "Server", .label = "net.Server" },
};

const Count = struct {
    /// Sites written with the full `std.<ns>.` prefix.
    direct: usize = 0,
    /// Sites reached through a local alias -- the ones a naive grep misses.
    aliased: usize = 0,
    files: usize = 0,
    /// Of the above, how many sit in a file the `tri` executable actually
    /// reaches. This is the number that decides whether the build advances;
    /// the whole-tree total does not.
    reachable: usize = 0,
    reachable_files: usize = 0,
};

/// Files reachable from src/tri/main.zig by following @import("...zig").
///
/// LIMITATION, stated because the last two plans in this migration went wrong
/// by trusting a count too far: this follows PATH imports only. A module
/// imported by name -- @import("tri27_cli") -- is wired up in build.zig, which
/// is not parsed here, so its subtree is invisible. The reachable set is
/// therefore a LOWER bound, and so is the IN-TRI column derived from it.
/// Two plans in this migration were built on whole-tree counts and both
/// mis-ranked the work: 140 argsAlloc sites looked like the top priority and
/// turned out to be one per main() across 141 OTHER executables, none of them
/// the tri binary.
const Reach = struct {
    set: std.StringHashMap(void),

    fn init(gpa: std.mem.Allocator) Reach {
        return .{ .set = std.StringHashMap(void).init(gpa) };
    }

    fn deinit(r: *Reach, gpa: std.mem.Allocator) void {
        var it = r.set.keyIterator();
        while (it.next()) |k| gpa.free(k.*);
        r.set.deinit();
    }

    fn contains(r: *const Reach, path: []const u8) bool {
        return r.set.contains(path);
    }

    /// Walks the import graph breadth-first from `root`.
    fn build(gpa: std.mem.Allocator, io: std.Io, root: []const u8) !Reach {
        var r: Reach = .init(gpa);
        var queue: std.ArrayList([]const u8) = .empty;
        defer queue.deinit(gpa);

        try r.set.put(try gpa.dupe(u8, root), {});
        try queue.append(gpa, try gpa.dupe(u8, root));

        var head: usize = 0;
        while (head < queue.items.len) : (head += 1) {
            const cur = queue.items[head];
            const src = std.Io.Dir.cwd().readFileAlloc(io, cur, gpa, .limited(8 * 1024 * 1024)) catch continue;
            defer gpa.free(src);

            const dir = std.fs.path.dirname(cur) orelse ".";
            var i: usize = 0;
            while (std.mem.indexOfPos(u8, src, i, "@import(\"")) |at| {
                const start = at + "@import(\"".len;
                const end = std.mem.indexOfPos(u8, src, start, "\"") orelse break;
                const name = src[start..end];
                i = end + 1;
                if (!std.mem.endsWith(u8, name, ".zig")) continue;

                const joined = try std.fs.path.join(gpa, &.{ dir, name });
                defer gpa.free(joined);
                const norm = try normalize(gpa, joined);
                if (r.set.contains(norm)) {
                    gpa.free(norm);
                    continue;
                }
                // Only follow it if it is a real file.
                std.Io.Dir.cwd().access(io, norm, .{}) catch {
                    gpa.free(norm);
                    continue;
                };
                try r.set.put(norm, {});
                try queue.append(gpa, try gpa.dupe(u8, norm));
            }
        }
        for (queue.items) |q| gpa.free(q);
        return r;
    }
};

/// Collapses `a/b/../c` to `a/c` so the same file is not counted twice under
/// two spellings.
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

/// Strips line comments and double-quoted string literals, replacing them with
/// spaces so column positions are preserved and nothing inside them can match.
fn stripNonCode(gpa: std.mem.Allocator, src: []const u8) ![]u8 {
    const out = try gpa.dupe(u8, src);
    var i: usize = 0;
    while (i < out.len) {
        if (out[i] == '/' and i + 1 < out.len and out[i + 1] == '/') {
            while (i < out.len and out[i] != '\n') : (i += 1) out[i] = ' ';
        } else if (out[i] == '"') {
            out[i] = ' ';
            i += 1;
            while (i < out.len and out[i] != '"' and out[i] != '\n') : (i += 1) {
                // A backslash escapes the next byte, including a quote.
                if (out[i] == '\\' and i + 1 < out.len) {
                    out[i] = ' ';
                    i += 1;
                }
                out[i] = ' ';
            }
            if (i < out.len and out[i] == '"') out[i] = ' ';
            i += 1;
        } else i += 1;
    }
    return out;
}

/// Finds `const <name> = std.<namespace>;` and returns the alias for one
/// namespace, or null when the file always writes the prefix out.
fn aliasFor(code: []const u8, namespace: []const u8, buf: []u8) ?[]const u8 {
    const needle = std.fmt.bufPrint(buf, " = std.{s};", .{namespace}) catch return null;
    const at = std.mem.indexOf(u8, code, needle) orelse return null;

    // Walk back over the identifier that precedes " = std.<ns>;".
    var end = at;
    while (end > 0 and code[end - 1] == ' ') end -= 1;
    var start = end;
    while (start > 0 and (std.ascii.isAlphanumeric(code[start - 1]) or code[start - 1] == '_')) start -= 1;
    if (start == end) return null;
    return code[start..end];
}

/// Counts non-overlapping occurrences of `prefix ++ member` where the match is
/// not itself preceded by an identifier character (so `mytime.timestamp` does
/// not count as `time.timestamp`).
fn countSites(code: []const u8, prefix: []const u8, member: []const u8, buf: []u8) usize {
    const needle = std.fmt.bufPrint(buf, "{s}{s}", .{ prefix, member }) catch return 0;
    var n: usize = 0;
    var i: usize = 0;
    while (std.mem.indexOfPos(u8, code, i, needle)) |at| {
        const before_ok = at == 0 or !(std.ascii.isAlphanumeric(code[at - 1]) or
            code[at - 1] == '_' or code[at - 1] == '.');
        if (before_ok) n += 1;
        i = at + needle.len;
    }
    return n;
}

pub fn main(init: std.process.Init.Minimal) !void {
    _ = init;
    var gpa_state: std.heap.DebugAllocator(.{}) = .init;
    defer _ = gpa_state.deinit();
    const gpa = gpa_state.allocator();

    var threaded: std.Io.Threaded = .init(gpa, .{});
    defer threaded.deinit();
    const io = threaded.io();

    var counts = [_]Count{.{}} ** axes.len;
    var alias_files: usize = 0;
    var scanned: usize = 0;

    var reach = try Reach.build(gpa, io, "src/tri/main.zig");
    defer reach.deinit(gpa);

    for ([_][]const u8{ "src", "tools" }) |root_name| {
        var root = std.Io.Dir.cwd().openDir(io, root_name, .{ .iterate = true }) catch continue;
        defer root.close(io);
        try walk(gpa, io, root, root_name, &counts, &alias_files, &scanned, &reach);
    }

    var stdout_buf: [4096]u8 = undefined;
    var w = std.Io.File.stdout().writerStreaming(io, &stdout_buf);
    const out = &w.interface;

    try out.print("scanned {d} .zig files; {d} of them alias a std namespace\n", .{ scanned, alias_files });
    try out.print("{d} files are reachable from src/tri/main.zig\n\n", .{reach.set.count()});
    try out.print("{s:<26} {s:>7} {s:>8} {s:>7} {s:>6} {s:>10} {s:>6}\n", .{
        "axis", "direct", "aliased", "total", "files", "IN-TRI", "files",
    });
    try out.print("{s:-<74}\n", .{""});

    var grand: usize = 0;
    var hidden: usize = 0;
    var in_tri: usize = 0;
    for (axes, counts) |a, c| {
        if (c.direct + c.aliased == 0) continue;
        try out.print("{s:<26} {d:>7} {d:>8} {d:>7} {d:>6} {d:>10} {d:>6}\n", .{
            a.label, c.direct, c.aliased, c.direct + c.aliased, c.files, c.reachable, c.reachable_files,
        });
        grand += c.direct + c.aliased;
        hidden += c.aliased;
        in_tri += c.reachable;
    }
    try out.print("{s:-<74}\n", .{""});
    try out.print("{s:<26} {d:>23} {d:>6} {d:>10}\n", .{ "TOTAL", grand, scanned, in_tri });
    try out.print("\n{d} of {d} sites ({d}%) are reachable ONLY through an alias --\n", .{
        hidden, grand, if (grand == 0) 0 else hidden * 100 / grand,
    });
    try out.print("a grep for the `std.` spelling alone reports every one of them as zero.\n\n", .{});
    try out.print("IN-TRI is the column that decides whether `zig build tri-compile` advances:\n", .{});
    try out.print("{d} of {d} sites ({d}%) are in files the tri binary actually reaches.\n", .{
        in_tri, grand, if (grand == 0) 0 else in_tri * 100 / grand,
    });
    try out.print("The rest belong to other build targets and cannot block this build.\n\n", .{});
    try out.print("CAVEAT: reachability follows @import(\"path.zig\") only. Imports by MODULE\n", .{});
    try out.print("name -- @import(\"tri27_cli\"), @import(\"tri_time\") -- are declared in\n", .{});
    try out.print("build.zig and are NOT followed, so IN-TRI is a LOWER bound. Treat it as\n", .{});
    try out.print("\"at least this much blocks the build\", never as the complete set.\n", .{});
    try out.flush();
}

fn walk(
    gpa: std.mem.Allocator,
    io: std.Io,
    dir: std.Io.Dir,
    prefix: []const u8,
    counts: *[axes.len]Count,
    alias_files: *usize,
    scanned: *usize,
    reach: *const Reach,
) !void {
    var it = dir.iterate();
    while (try it.next(io)) |entry| {
        if (entry.name.len > 0 and entry.name[0] == '.') continue;
        if (entry.kind == .directory) {
            // Generators emit Zig as string literals; their "sites" are data.
            if (std.mem.eql(u8, entry.name, "codegen")) continue;
            if (std.mem.eql(u8, entry.name, "zig-out")) continue;
            var sub = dir.openDir(io, entry.name, .{ .iterate = true }) catch continue;
            defer sub.close(io);
            const child = try std.fmt.allocPrint(gpa, "{s}/{s}", .{ prefix, entry.name });
            defer gpa.free(child);
            try walk(gpa, io, sub, child, counts, alias_files, scanned, reach);
            continue;
        }
        if (entry.kind != .file) continue;
        if (!std.mem.endsWith(u8, entry.name, ".zig")) continue;

        const raw = dir.readFileAlloc(io, entry.name, gpa, .limited(8 * 1024 * 1024)) catch continue;
        defer gpa.free(raw);
        const code = try stripNonCode(gpa, raw);
        defer gpa.free(code);

        scanned.* += 1;
        const rel = try std.fmt.allocPrint(gpa, "{s}/{s}", .{ prefix, entry.name });
        defer gpa.free(rel);
        const in_tri = reach.contains(rel);
        var saw_alias = false;
        var nbuf: [128]u8 = undefined;
        var abuf: [64]u8 = undefined;

        for (axes, 0..) |a, idx| {
            var pbuf: [64]u8 = undefined;
            const direct_prefix = std.fmt.bufPrint(&pbuf, "std.{s}.", .{a.namespace}) catch continue;
            const d = countSites(code, direct_prefix, a.member, &nbuf);

            var al: usize = 0;
            if (aliasFor(code, a.namespace, &abuf)) |alias| {
                saw_alias = true;
                var apbuf: [80]u8 = undefined;
                const alias_prefix = std.fmt.bufPrint(&apbuf, "{s}.", .{alias}) catch continue;
                al = countSites(code, alias_prefix, a.member, &nbuf);
            }

            if (d + al > 0) {
                counts[idx].direct += d;
                counts[idx].aliased += al;
                counts[idx].files += 1;
                if (in_tri) {
                    counts[idx].reachable += d + al;
                    counts[idx].reachable_files += 1;
                }
            }
        }
        if (saw_alias) alias_files.* += 1;
    }
}
