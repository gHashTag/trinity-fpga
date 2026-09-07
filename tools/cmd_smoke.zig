//! Runs every `tri` command against a scratch tree and reports what happened.
//!
//!   zig build tri-compile && zig run tools/cmd_smoke.zig -lc
//!
//! WHY THIS EXISTS (#763). After the Zig 0.16 migration `tri` built and 142
//! commands enumerated, but only SIX had ever been executed end to end. The
//! rest were run with `--help` only, because running them for real would have
//! pushed commits, spawned cloud agents, or spent tokens against live
//! credentials. "It builds" is not "it works": the migration changed the
//! behaviour of nine stdlib families, and a clean build says nothing about
//! any of them.
//!
//! THE ISOLATION IS THE WHOLE POINT. Four independent measures, because any
//! one of them alone is not enough to run `tri git commit` without fear:
//!
//!   1. cwd is a fresh temp directory with its own `git init` and `.trinity/`.
//!      Every state path in `tri` is relative to cwd, so nothing it writes can
//!      escape.
//!   2. HOME points at that same directory, so `~/.claude`, `~/.config` and
//!      friends resolve inside the sandbox rather than to the real user.
//!   3. The child environment is REBUILT from a small allowlist rather than
//!      filtered. 93 environment variables are read across this tree and 31 of
//!      them are credentials; a denylist would silently miss the next one
//!      somebody adds. With no token present, a command that would call an API
//!      fails at authentication instead of succeeding.
//!   4. A watchdog kills anything still running after a timeout, so `serve`
//!      and the daemons cannot hang the run.
//!
//! WHAT COUNTS AS A FAILURE. A non-zero exit is NOT one: `tri fib` correctly
//! exits 2 asking for an argument, and several commands are honest
//! `NotImplemented` stubs. What this gate fails on is a CRASH (a signal --
//! segfault, abort, an unhandled panic) or a TIMEOUT, because those are what a
//! botched migration produces and neither can be explained away.
//!
//! phi^2 + 1/phi^2 = 3 = TRINITY

const std = @import("std");
const tri_time = @import("tri_time");
const tri_env = @import("tri_env");

/// Seconds a single command may run before the watchdog kills it.
const timeout_s: u64 = 20;

/// Rebuilt, not filtered -- see the header. TERM is included so colour output
/// takes its normal path rather than a fallback nobody exercises.
const env_allowlist = [_][]const u8{ "PATH", "TMPDIR", "LANG", "TERM" };

const Outcome = enum {
    ok, // exited 0
    nonzero, // exited non-zero: usually a Usage: line or a NotImplemented stub
    crashed, // killed by a signal -- a real defect
    timed_out, // still running after timeout_s -- a real defect
    spawn_failed,

    fn isFailure(o: Outcome) bool {
        return o == .crashed or o == .timed_out or o == .spawn_failed;
    }
};

const Result = struct {
    name: []const u8,
    outcome: Outcome,
    code: u8 = 0,
    first_line: []const u8 = "",
};

/// Watchdog state. `done` is set by the main thread the moment `wait` returns,
/// so a command that finishes quickly does not get killed by a late timer.
///
/// THE KILL GOES THROUGH LIBC, NOT `Child.kill`, and that is not a shortcut.
/// There is an unavoidable race between this thread deciding to kill and the
/// main thread reaping the child: the pid can be reaped in the window between
/// the `done` check and the kill. `Child.kill` answers ECHILD there by
/// PANICKING -- 0.16's Threaded backend classes it as `errnoBug`, "programmer
/// bug caused syscall error: CHILD" -- which turns a benign race into a crash
/// of the harness itself. Found by running two copies of this tool at once.
///
/// libc kill() answers a stale pid with ESRCH and a -1 return, which is
/// exactly the "already gone, nothing to do" this needs.
const Watchdog = struct {
    child: *std.process.Child,
    io: std.Io,
    done: *std.atomic.Value(bool),
    fired: *std.atomic.Value(bool),

    fn run(w: Watchdog) void {
        var waited: u64 = 0;
        while (waited < timeout_s * 1000) : (waited += 50) {
            if (w.done.load(.acquire)) return;
            tri_time.sleep(50 * std.time.ns_per_ms);
        }
        if (w.done.load(.acquire)) return;
        const pid = w.child.id orelse return;
        w.fired.store(true, .release);
        _ = c_kill.kill(pid, 9); // SIGKILL; ESRCH if already reaped, harmless
    }
};

const c_kill = struct {
    extern "c" fn kill(pid: i32, sig: c_int) c_int;
};

pub fn main(init: std.process.Init.Minimal) !void {
    var gpa_state: std.heap.DebugAllocator(.{}) = .init;
    defer _ = gpa_state.deinit();
    const gpa = gpa_state.allocator();

    var threaded: std.Io.Threaded = .init(gpa, .{});
    defer threaded.deinit();
    const io = threaded.io();

    const args = try init.args.toSlice(gpa);
    defer gpa.free(args);

    const tri_path = "zig-out/bin/tri";
    std.Io.Dir.cwd().access(io, tri_path, .{}) catch {
        std.debug.print("cmd_smoke: {s} not found -- run `zig build tri-compile` first\n", .{tri_path});
        return error.TriNotBuilt;
    };
    // The child runs with a different cwd, so the path must be absolute.
    // realPathFile resolves a sub-path and returns its LENGTH, not a slice.
    const exe = try std.Io.Dir.cwd().realPathFileAlloc(io, tri_path, gpa);
    defer gpa.free(exe);

    const commands = try enumerateCommands(gpa, io, exe);
    defer {
        for (commands) |c| gpa.free(c);
        gpa.free(commands);
    }
    if (commands.len == 0) {
        // A derived list that matches nothing would run zero commands and
        // report success. An empty result is a failure, not a pass.
        std.debug.print("cmd_smoke: parsed 0 commands from --help. Refusing to report a pass.\n", .{});
        return error.NoCommandsParsed;
    }

    var results = try gpa.alloc(Result, commands.len);
    defer {
        for (results) |r| gpa.free(r.first_line);
        gpa.free(results);
    }

    std.debug.print("running {d} commands, {d}s timeout, isolated cwd + HOME, no credentials\n\n", .{ commands.len, timeout_s });

    for (commands, 0..) |cmd, i| {
        results[i] = try runOne(gpa, io, exe, cmd);
        const mark: []const u8 = switch (results[i].outcome) {
            .ok => "ok  ",
            .nonzero => "rc  ",
            .crashed => "CRASH",
            .timed_out => "HANG",
            .spawn_failed => "SPAWN",
        };
        std.debug.print("  {s} {s:<26} {s}\n", .{ mark, cmd, results[i].first_line });
    }

    var counts = [_]usize{0} ** 5;
    for (results) |r| counts[@intFromEnum(r.outcome)] += 1;

    std.debug.print("\n  ok        {d}\n  non-zero  {d}\n  CRASHED   {d}\n  TIMED OUT {d}\n  no-spawn  {d}\n", .{
        counts[0], counts[1], counts[2], counts[3], counts[4],
    });

    var failed: usize = 0;
    for (results) |r| {
        if (r.outcome.isFailure()) {
            failed += 1;
            std.debug.print("  FAIL {s}: {s}\n", .{ r.name, @tagName(r.outcome) });
        }
    }
    if (failed > 0) {
        std.debug.print("\n{d} command(s) crashed, hung, or could not start.\n", .{failed});
        return error.CommandsFailed;
    }
    std.debug.print("\nNo command crashed or hung. Non-zero exits are reported, not failed on:\n", .{});
    std.debug.print("a Usage: line and a NotImplemented stub are both correct behaviour.\n", .{});
}

/// Parses top-level command names out of `tri --help`.
fn enumerateCommands(gpa: std.mem.Allocator, io: std.Io, exe: []const u8) ![][]const u8 {
    const res = try std.process.run(gpa, io, .{
        .argv = &.{ exe, "--help" },
        .stdout_limit = .limited(1 << 20),
        .stderr_limit = .limited(1 << 20),
    });
    defer gpa.free(res.stdout);
    defer gpa.free(res.stderr);

    var out: std.ArrayList([]const u8) = .empty;
    errdefer {
        for (out.items) |x| gpa.free(x);
        out.deinit(gpa);
    }
    var seen: std.StringHashMap(void) = .init(gpa);
    defer seen.deinit();

    // `tri --help` writes to STDERR, not stdout. Reading only stdout parsed
    // zero commands -- and the empty-result guard below caught it rather than
    // reporting a clean run over nothing, which is what it is there for.
    const help = if (res.stdout.len > res.stderr.len) res.stdout else res.stderr;
    var lines = std.mem.splitScalar(u8, help, '\n');
    while (lines.next()) |raw| {
        const line = stripAnsi(raw);
        // Command entries are indented by exactly two spaces and start with a
        // lowercase letter. Anything else is a heading or prose.
        if (!std.mem.startsWith(u8, line, "  ")) continue;
        if (line.len < 3 or line[2] == ' ') continue;
        var it = std.mem.tokenizeAny(u8, line, " \t");
        const name = it.next() orelse continue;
        if (name.len == 0 or !std.ascii.isLower(name[0])) continue;
        var ok = true;
        for (name) |c| {
            if (!std.ascii.isLower(c) and !std.ascii.isDigit(c) and c != '-') ok = false;
        }
        if (!ok) continue;
        if (seen.contains(name)) continue;
        const dup = try gpa.dupe(u8, name);
        try seen.put(dup, {});
        try out.append(gpa, dup);
    }
    return out.toOwnedSlice(gpa);
}

/// ANSI escapes would defeat the prefix match above; drop them in place.
fn stripAnsi(line: []const u8) []const u8 {
    var buf: [512]u8 = undefined;
    var n: usize = 0;
    var i: usize = 0;
    while (i < line.len and n < buf.len) {
        if (line[i] == 0x1b) {
            while (i < line.len and line[i] != 'm') i += 1;
            i += 1;
            continue;
        }
        buf[n] = line[i];
        n += 1;
        i += 1;
    }
    // Safe: callers only read it before the next call, and the parser above
    // finishes with each line before moving on.
    const S = struct {
        var scratch: [512]u8 = undefined;
    };
    @memcpy(S.scratch[0..n], buf[0..n]);
    return S.scratch[0..n];
}

fn runOne(gpa: std.mem.Allocator, io: std.Io, exe: []const u8, cmd: []const u8) !Result {
    const sandbox = try makeSandbox(gpa, io);
    defer gpa.free(sandbox);
    defer std.Io.Dir.cwd().deleteTree(io, sandbox) catch {};

    var env = try minimalEnv(gpa, sandbox);
    defer env.deinit();

    var child = std.process.spawn(io, .{
        .argv = &.{ exe, cmd },
        .cwd = .{ .path = sandbox },
        .environ_map = &env,
        .stdin = .ignore,
        .stdout = .pipe,
        .stderr = .pipe,
    }) catch return .{ .name = cmd, .outcome = .spawn_failed, .first_line = try gpa.dupe(u8, "") };

    var done: std.atomic.Value(bool) = .init(false);
    var fired: std.atomic.Value(bool) = .init(false);
    const wd = try std.Thread.spawn(.{}, Watchdog.run, .{Watchdog{
        .child = &child,
        .io = io,
        .done = &done,
        .fired = &fired,
    }});

    const term = child.wait(io) catch {
        done.store(true, .release);
        wd.join();
        return .{ .name = cmd, .outcome = .spawn_failed, .first_line = try gpa.dupe(u8, "") };
    };
    done.store(true, .release);
    wd.join();

    if (fired.load(.acquire)) {
        return .{ .name = cmd, .outcome = .timed_out, .first_line = try gpa.dupe(u8, "killed by watchdog") };
    }

    return switch (term) {
        .exited => |code| .{
            .name = cmd,
            .outcome = if (code == 0) .ok else .nonzero,
            .code = code,
            .first_line = try std.fmt.allocPrint(gpa, "exit {d}", .{code}),
        },
        // A signal is the outcome this gate exists to catch.
        else => .{
            .name = cmd,
            .outcome = .crashed,
            .first_line = try std.fmt.allocPrint(gpa, "{s}", .{@tagName(term)}),
        },
    };
}

/// A fresh temp directory holding a git repo and an empty `.trinity/`.
fn makeSandbox(gpa: std.mem.Allocator, io: std.Io) ![]u8 {
    var seed: [8]u8 = undefined;
    const ts = tri_time.nanoTimestamp();
    std.mem.writeInt(u64, &seed, @bitCast(@as(i64, @truncate(ts))), .little);

    const base = tri_env.getPosix("TMPDIR") orelse "/tmp";
    const dir = try std.fmt.allocPrint(gpa, "{s}/tri-smoke-{x}", .{ std.mem.trimEnd(u8, base, "/"), std.mem.readInt(u64, &seed, .little) });
    errdefer gpa.free(dir);

    try std.Io.Dir.createDirPath(std.Io.Dir.cwd(), io, dir);
    const trinity = try std.fmt.allocPrint(gpa, "{s}/.trinity", .{dir});
    defer gpa.free(trinity);
    try std.Io.Dir.createDirPath(std.Io.Dir.cwd(), io, trinity);

    // A git repo, so `tri git *` and anything reading HEAD has something real
    // to talk to that is not this repository.
    var git = std.process.spawn(io, .{
        .argv = &.{ "/usr/bin/git", "init", "-q", dir },
        .stdout = .ignore,
        .stderr = .ignore,
    }) catch return dir;
    _ = git.wait(io) catch {};
    return dir;
}

/// Built from an allowlist. HOME is redirected INTO the sandbox so that a
/// command reaching for `~/.claude` cannot find the real one.
fn minimalEnv(gpa: std.mem.Allocator, sandbox: []const u8) !std.process.Environ.Map {
    var map: std.process.Environ.Map = .init(gpa);
    errdefer map.deinit();
    for (env_allowlist) |name| {
        const v = tri_env.getPosix(name) orelse continue;
        try map.put(name, v);
    }
    try map.put("HOME", sandbox);
    // Marks the run for anything that wants to behave differently under test,
    // and makes the sandbox visible in a stray log line.
    try map.put("TRI_SMOKE_SANDBOX", sandbox);
    return map;
}
