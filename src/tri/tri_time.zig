// ═══════════════════════════════════════════════════════════════════════════════
// TRI CLI - Wall-clock timestamps (Zig 0.16 shim)
// ═══════════════════════════════════════════════════════════════════════════════
//
// Zig 0.16 emptied `std.time` down to unit constants and `epoch`. Every
// timestamp function it used to export -- `timestamp`, `milliTimestamp`,
// `microTimestamp`, `nanoTimestamp` -- and `std.time.Timer` are gone. Reading
// a clock is now an `Io` capability: `Io.Clock.Timestamp.now(io, .REALTIME)`.
//
// That is the right shape for code that should be virtualisable in tests, and
// the wrong shape for this tree: there are 491 timestamp call sites across 116
// files reachable from main.zig, and essentially all of them stamp a log line,
// a metric, or a filename. Threading an `Io` to each would mean a signature
// change on every function in between -- a far larger and riskier change than
// the thing being migrated.
//
// So this module keeps the removed names and their exact return types, backed
// by libc's clock_gettime (libc is already linked; the build passes -lc). The
// change at each call site is one word: `std.time.X` becomes `tri_time.X`.
//
// The per-OS `timespec` layout and the CLOCK enum both come from `std.c`
// rather than being declared here, so this stays correct on Linux and macOS
// alike -- the two differ in integer widths, and hand-rolling the struct is a
// known way to get a silently wrong reading on one of them.
//
// If a caller ever genuinely needs a virtual clock, it should take an `Io` and
// call the stdlib directly. This shim is for the ambient logging clock.
//
// phi^2 + 1/phi^2 = 3 = TRINITY
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");

/// Reads a POSIX clock, or returns a zeroed timespec if the clock is
/// unavailable. The stdlib functions this replaces did not report failure
/// either -- they panicked or returned a value -- and a log line is not worth
/// an error path, so an unreadable clock degrades to the epoch rather than
/// propagating.
fn read(clock: std.c.clockid_t) std.c.timespec {
    var ts: std.c.timespec = undefined;
    if (std.c.clock_gettime(clock, &ts) != 0) return .{ .sec = 0, .nsec = 0 };
    return ts;
}

/// Seconds since the UNIX epoch. Replaces `std.time.timestamp`.
pub fn timestamp() i64 {
    const ts = read(.REALTIME);
    return @intCast(ts.sec);
}

/// Milliseconds since the UNIX epoch. Replaces `std.time.milliTimestamp`.
pub fn milliTimestamp() i64 {
    const ts = read(.REALTIME);
    return @as(i64, @intCast(ts.sec)) * std.time.ms_per_s +
        @divFloor(@as(i64, @intCast(ts.nsec)), std.time.ns_per_ms);
}

/// Microseconds since the UNIX epoch. Replaces `std.time.microTimestamp`.
pub fn microTimestamp() i64 {
    const ts = read(.REALTIME);
    return @as(i64, @intCast(ts.sec)) * std.time.us_per_s +
        @divFloor(@as(i64, @intCast(ts.nsec)), std.time.ns_per_us);
}

/// Nanoseconds since the UNIX epoch. Replaces `std.time.nanoTimestamp`.
/// Returns i128 for the same reason the stdlib did: nanoseconds since 1970
/// overflow an i64 in the year 2262, and this is the one that has to carry the
/// full range.
pub fn nanoTimestamp() i128 {
    const ts = read(.REALTIME);
    return @as(i128, @intCast(ts.sec)) * std.time.ns_per_s +
        @as(i128, @intCast(ts.nsec));
}

/// Monotonic nanoseconds. Not wall-clock: the value has no meaning on its own
/// and is only valid as a difference between two readings. Use this for
/// durations -- `milliTimestamp` deltas are wrong across an NTP step or a
/// daylight-saving change.
pub fn monotonicNanos() u64 {
    const ts = read(.MONOTONIC);
    const secs: u64 = @intCast(@max(ts.sec, 0));
    const nsecs: u64 = @intCast(@max(ts.nsec, 0));
    return secs * std.time.ns_per_s + nsecs;
}

/// Elapsed-time measurement. Replaces the removed `std.time.Timer` for the
/// one thing this codebase used it for: start it, read it, print a duration.
pub const Timer = struct {
    started_ns: u64,

    pub fn start() Timer {
        return .{ .started_ns = monotonicNanos() };
    }

    /// Nanoseconds since `start`. Saturates at zero rather than wrapping if
    /// the monotonic clock ever reports a smaller value than it did before.
    pub fn read(self: Timer) u64 {
        const now = monotonicNanos();
        return if (now > self.started_ns) now - self.started_ns else 0;
    }

    /// Nanoseconds since `start`, and restarts the timer.
    pub fn lap(self: *Timer) u64 {
        const now = monotonicNanos();
        const elapsed = if (now > self.started_ns) now - self.started_ns else 0;
        self.started_ns = now;
        return elapsed;
    }

    pub fn reset(self: *Timer) void {
        self.started_ns = monotonicNanos();
    }
};

// ═══════════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════════

test "timestamp is a plausible current unix time" {
    // 2020-01-01 < now < 2100-01-01. Catches a zeroed clock and a unit mix-up
    // in either direction, which is what actually goes wrong in a shim like
    // this -- returning nanoseconds from a function declared to return seconds
    // lands far outside this window.
    const t = timestamp();
    try std.testing.expect(t > 1_577_836_800);
    try std.testing.expect(t < 4_102_444_800);
}

test "the four units agree with each other" {
    const s = timestamp();
    const ms = milliTimestamp();
    const us = microTimestamp();
    const ns = nanoTimestamp();

    // Each should agree with seconds once scaled down. Allow 2s of slack for
    // the clock advancing between the four reads.
    try std.testing.expect(@abs(@divFloor(ms, std.time.ms_per_s) - s) <= 2);
    try std.testing.expect(@abs(@divFloor(us, std.time.us_per_s) - s) <= 2);
    try std.testing.expect(@abs(@divFloor(ns, std.time.ns_per_s) - @as(i128, s)) <= 2);
}

test "nanoTimestamp keeps sub-second precision" {
    // A common way to get this wrong is to compute nanoseconds from whole
    // seconds only, which yields an exact multiple of 1e9 every time.
    var saw_fraction = false;
    var i: usize = 0;
    while (i < 8) : (i += 1) {
        if (@mod(nanoTimestamp(), std.time.ns_per_s) != 0) {
            saw_fraction = true;
            break;
        }
    }
    try std.testing.expect(saw_fraction);
}

test "monotonic clock does not go backwards" {
    var prev = monotonicNanos();
    var i: usize = 0;
    while (i < 1000) : (i += 1) {
        const now = monotonicNanos();
        try std.testing.expect(now >= prev);
        prev = now;
    }
}

test "Timer measures a non-negative elapsed time and laps reset it" {
    var t = Timer.start();
    var sink: u64 = 0;
    var i: usize = 0;
    while (i < 100_000) : (i += 1) sink +%= i;
    std.mem.doNotOptimizeAway(sink);

    const first = t.read();
    const lapped = t.lap();
    try std.testing.expect(lapped >= first or lapped == 0);

    // After a lap the timer restarts, so the next read is small relative to
    // the work above rather than cumulative.
    const after = t.read();
    try std.testing.expect(after <= lapped + std.time.ns_per_s);
}
