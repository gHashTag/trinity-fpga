// ═══════════════════════════════════════════════════════════════════════════════
// TRI CLI - Cryptographic randomness (Zig 0.16 shim)
// ═══════════════════════════════════════════════════════════════════════════════
//
// Zig 0.16 removed `std.crypto.random`. There is no replacement inside
// `std.crypto`: seeding is now the caller's problem, because the stdlib no
// longer wants a hidden global CSPRNG initialised behind your back.
//
// This tree has 52 call sites, all of the shape `std.crypto.random.float(f64)`
// or `.intRangeAtMost(...)`, in code that picks a jitter, a retry delay, or an
// HNSW level. They want "some good-quality randomness", not a specific
// generator, and none of them is in a position to carry a seed.
//
// So: a lazily seeded ChaCha CSPRNG, seeded from the system entropy source --
// `arc4random_buf` where the target has it, `/dev/urandom` otherwise. That
// split is not decoration: on Linux std.c.arc4random_buf is gated behind
// glibc >= 2.36 and resolves to `void` below it, which is a COMPILE error at
// the call rather than a runtime fallback. See systemEntropy.
//
// The one shape change at the call site is a pair of parentheses:
// `std.crypto.random.float(f64)` becomes `tri_rand.random().float(f64)`.
// It has to be a function rather than a `const` because the backing state is
// initialised on first use, and a `const` cannot be.
//
// NOT reproducible by design. If a caller ever needs a seeded, repeatable
// sequence -- a benchmark, a fuzz corpus, a test -- it should declare its own
// `std.Random.DefaultPrng` with an explicit seed rather than reach for this.
//
// phi^2 + 1/phi^2 = 3 = TRINITY
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");

var g_csprng: std.Random.DefaultCsprng = undefined;
var g_ready: bool = false;

/// Guards first-use seeding. Same compare-exchange spinlock as tri_io, and for
/// the same reason: std.Thread.Mutex is gone and std.Io.Mutex would drag an Io
/// into a module that has no other need for one.
var g_lock: std.atomic.Value(bool) = .init(false);

/// The process CSPRNG. Replaces the removed `std.crypto.random`.
pub fn random() std.Random {
    if (!@atomicLoad(bool, &g_ready, .acquire)) seed();
    return g_csprng.random();
}

/// Fills `dest` from the system entropy source.
///
/// `std.c.arc4random_buf` is NOT portable the way it looks: on Linux it is
/// gated behind glibc >= 2.36, and resolves to `void` otherwise -- which is a
/// compile error at the call, not a runtime fallback. Cross-compiling to
/// x86_64-linux-gnu is what surfaced it; everything here had been measured on
/// macOS, where the symbol always exists.
///
/// So: use it when the target actually has it, and read /dev/urandom when it
/// does not. The latter needs no version gate and exists on every POSIX system
/// this runs on.
fn systemEntropy(dest: []u8) void {
    if (@TypeOf(std.c.arc4random_buf) != void) {
        std.c.arc4random_buf(dest.ptr, dest.len);
        return;
    }
    const fd = c_rand.open("/dev/urandom", 0, 0);
    if (fd >= 0) {
        defer _ = c_rand.close(fd);
        var off: usize = 0;
        while (off < dest.len) {
            const n = c_rand.read(fd, dest[off..].ptr, dest.len - off);
            if (n <= 0) break;
            off += @intCast(n);
        }
        if (off == dest.len) return;
    }
    // Entropy is unavailable. Rather than seed from a constant and look
    // random, make the degradation visible.
    @panic("tri_rand: no system entropy source (arc4random_buf absent and /dev/urandom unreadable)");
}

const c_rand = struct {
    extern "c" fn open(path: [*:0]const u8, flags: c_int, mode: c_uint) c_int;
    extern "c" fn read(fd: c_int, buf: [*]u8, n: usize) isize;
    extern "c" fn close(fd: c_int) c_int;
};

fn seed() void {
    while (g_lock.cmpxchgWeak(false, true, .acquire, .monotonic) != null) {
        std.atomic.spinLoopHint();
    }
    defer g_lock.store(false, .release);

    // Re-check under the lock; another thread may have seeded already.
    if (@atomicLoad(bool, &g_ready, .acquire)) return;

    var s: [std.Random.DefaultCsprng.secret_seed_length]u8 = undefined;
    systemEntropy(&s);
    g_csprng = std.Random.DefaultCsprng.init(s);
    @atomicStore(bool, &g_ready, true, .release);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════════

test "float stays in [0,1) and is not constant" {
    var saw_difference = false;
    var first = random().float(f64);
    try std.testing.expect(first >= 0.0 and first < 1.0);

    var i: usize = 0;
    while (i < 64) : (i += 1) {
        const v = random().float(f64);
        try std.testing.expect(v >= 0.0 and v < 1.0);
        if (v != first) saw_difference = true;
    }
    // A shim that returned a fixed value would satisfy the range check alone.
    try std.testing.expect(saw_difference);
    _ = &first;
}

test "intRangeAtMost respects both bounds" {
    var i: usize = 0;
    while (i < 512) : (i += 1) {
        const v = random().intRangeAtMost(u32, 10, 20);
        try std.testing.expect(v >= 10 and v <= 20);
    }
}

test "a single-value range returns that value" {
    try std.testing.expectEqual(@as(u8, 7), random().intRangeAtMost(u8, 7, 7));
}

test "output covers the range rather than sticking to one end" {
    // Catches a seeding bug that leaves the generator in a degenerate state:
    // 400 draws from [0,9] hitting fewer than 5 distinct values would be
    // vanishingly unlikely for a working CSPRNG.
    var seen = [_]bool{false} ** 10;
    var i: usize = 0;
    while (i < 400) : (i += 1) seen[random().intRangeAtMost(usize, 0, 9)] = true;

    var distinct: usize = 0;
    for (seen) |b| {
        if (b) distinct += 1;
    }
    try std.testing.expect(distinct >= 5);
}

test "bytes fills the whole buffer" {
    var buf = [_]u8{0} ** 64;
    random().bytes(&buf);
    var nonzero: usize = 0;
    for (buf) |b| {
        if (b != 0) nonzero += 1;
    }
    // An unwritten buffer stays all-zero; a filled one essentially never does.
    try std.testing.expect(nonzero > 40);
}
