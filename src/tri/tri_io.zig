// ═══════════════════════════════════════════════════════════════════════════════
// TRI CLI - Process-wide Io handle (Zig 0.16)
// ═══════════════════════════════════════════════════════════════════════════════
//
// Zig 0.16 puts file I/O behind an `Io`. Where an Io can be threaded through a
// call chain, it should be: an explicit parameter is clearer, and it is what
// makes the I/O substitutable in a test. Most of this migration does exactly
// that -- ContextManager, Logger, runGenCommand and friends all take one.
//
// This module is for the places where threading is not available. `tri` is one
// executable built from several build modules (root, tri27_cli, the vibeec
// chat modules), and a leaf in one of those modules is reached through call
// chains that cross module boundaries. Giving those leaves an Io parameter
// means changing every signature between here and main, in modules that have
// no other reason to know about Io.
//
// So: main installs the process's Io at startup, and those leaves ask for it.
// There is still exactly one Io in the process -- `install` publishes the same
// `std.Io.Threaded` main already builds, rather than creating a second one.
//
// The lazy fallback exists for unit tests and for any entry point that reaches
// this code without going through main. It is not the intended path.
//
// When touching code that already receives an `io` parameter, use that
// parameter. Reaching for `tri_io.get()` when one is in scope defeats the
// point of the migration.
//
// phi^2 + 1/phi^2 = 3 = TRINITY
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");

var g_io: ?std.Io = null;

/// Backing implementation for the lazy fallback. Declared at module scope so
/// its address is stable -- `Io.Threaded.io()` hands out a pointer to it, so
/// it must not live on a stack frame or inside an optional that gets copied.
var g_threaded: std.Io.Threaded = undefined;
var g_threaded_ready: bool = false;

/// Guards first-time initialisation. A compare-exchange spinlock rather than a
/// mutex because std.Thread.Mutex is gone in 0.16 and std.Io.Mutex would need
/// the very Io this function exists to produce.
var g_lock: std.atomic.Value(bool) = .init(false);

fn lock() void {
    while (g_lock.cmpxchgWeak(false, true, .acquire, .monotonic) != null) {
        std.atomic.spinLoopHint();
    }
}

fn unlock() void {
    g_lock.store(false, .release);
}

/// Publish the process's Io. Call once, from main, immediately after building
/// it and before dispatching any command.
pub fn install(io: std.Io) void {
    lock();
    defer unlock();
    g_io = io;
}

/// The process's Io.
///
/// Returns whatever `install` published. If nothing has been installed -- a
/// unit test, or an entry point that does not run main -- it builds a
/// thread-pool Io on the page allocator and keeps it for the life of the
/// process.
pub fn get() std.Io {
    if (g_io) |io| return io;

    lock();
    defer unlock();

    // Re-check under the lock: another thread may have installed or built one
    // between the fast path above and acquiring the lock.
    if (g_io) |io| return io;

    if (!g_threaded_ready) {
        g_threaded = .init(std.heap.page_allocator, .{});
        g_threaded_ready = true;
    }
    const io = g_threaded.io();
    g_io = io;
    return io;
}

/// True when main (or a test) has published an Io. Lets a caller tell the
/// real process Io apart from the lazily constructed fallback.
pub fn isInstalled() bool {
    return g_io != null;
}

/// Test-only: drop whatever is installed so the next `get` rebuilds. Not for
/// production code -- an Io handed out earlier stays valid, so resetting does
/// not invalidate existing users, but it does mean two Ios are live.
pub fn resetForTest() void {
    lock();
    defer unlock();
    g_io = null;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════════

test "get returns a usable Io without an install" {
    resetForTest();
    const io = get();

    // Exercise it rather than merely holding it: a handle that cannot open a
    // directory is not evidence of anything.
    var dir = try std.Io.Dir.cwd().openDir(io, ".", .{});
    dir.close(io);
}

test "get is stable across calls" {
    resetForTest();
    const a = get();
    const b = get();
    try std.testing.expect(a.userdata == b.userdata);
}

test "install publishes the given Io and isInstalled reports it" {
    resetForTest();
    try std.testing.expect(!isInstalled());

    var threaded: std.Io.Threaded = .init(std.testing.allocator, .{});
    defer threaded.deinit();
    const mine = threaded.io();

    install(mine);
    try std.testing.expect(isInstalled());
    try std.testing.expect(get().userdata == mine.userdata);

    // Leave the global clean for whatever runs next.
    resetForTest();
}

test "install wins over the lazy fallback" {
    resetForTest();
    const lazy = get();

    var threaded: std.Io.Threaded = .init(std.testing.allocator, .{});
    defer threaded.deinit();
    const mine = threaded.io();

    install(mine);
    try std.testing.expect(get().userdata != lazy.userdata);
    try std.testing.expect(get().userdata == mine.userdata);

    resetForTest();
}
