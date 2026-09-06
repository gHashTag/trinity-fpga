//! A mutex with the pre-0.16 shape, so the CLI keeps compiling.
//!
//! Zig 0.16 removed every synchronisation primitive from `std.Thread` --
//! Mutex, Condition, RwLock, Semaphore, Futex are all gone; only `yield()`
//! remains. The replacement is `std.Io.Mutex`, whose `lock(io)` takes an `Io`
//! instance and returns `Cancelable!void`. Adopting it properly means
//! threading an `Io` through to all 78 call sites in this tree, which is a
//! real migration and not a build fix.
//!
//! This is the build fix: `std.atomic.Mutex` (a lock-free single-owner
//! `tryLock`/`unlock` pair) plus a yielding spin, exposing the `lock()` /
//! `unlock()` shape the existing code already uses.
//!
//! It is honest about what it is: a spin lock. That is acceptable here
//! because every use in this tree is a CLI-lifetime guard around cheap
//! critical sections -- a log line, a cache entry, a counter -- held for
//! microseconds under no real contention. It would NOT be acceptable for a
//! lock held across I/O or across a long computation, and if such a use
//! appears, that call site wants `std.Io.Mutex` rather than this.
//!
//! phi^2 + 1/phi^2 = 3 = TRINITY

const std = @import("std");

/// This tree is built with 0.15 today and must keep compiling if that moves,
/// so the shim picks per-version at compile time rather than committing to
/// either. `std.atomic.Mutex` does not exist in 0.15 and `std.Thread.Mutex`
/// does not exist in 0.16, so a shim naming only one of them relocates the
/// breakage instead of absorbing it -- which is what the first version of
/// this file did.
pub const Mutex = if (@hasDecl(std.Thread, "Mutex")) std.Thread.Mutex else SpinMutex;

/// 0.16 and later: `std.atomic.Mutex` is a lock-free single-owner
/// tryLock/unlock pair with no blocking acquire, so the wait is ours to write.
const SpinMutex = struct {
    state: std.atomic.Mutex = .unlocked,

    /// Block until the lock is acquired. Yields rather than spinning hot, so a
    /// waiter does not starve the holder on a single core.
    pub fn lock(self: *SpinMutex) void {
        while (!self.state.tryLock()) {
            std.Thread.yield() catch {};
        }
    }

    /// Acquire without blocking. True if the lock is now held by the caller.
    pub fn tryLock(self: *SpinMutex) bool {
        return self.state.tryLock();
    }

    /// Release. Asserts the lock is held, same as the std primitive.
    pub fn unlock(self: *SpinMutex) void {
        self.state.unlock();
    }
};

test "lock and unlock round-trip" {
    var m = Mutex{};
    m.lock();
    try std.testing.expect(!m.tryLock()); // held: a second acquire must fail
    m.unlock();
    try std.testing.expect(m.tryLock()); // released: it must succeed
    m.unlock();
}

test "default initialisation is unlocked" {
    // The code base writes both `Mutex{}` and `= .{}`; both must be usable
    // without an explicit init call, as std.Thread.Mutex was.
    var m: Mutex = .{};
    try std.testing.expect(m.tryLock());
    m.unlock();
}

test "mutual exclusion holds under real contention" {
    // The two tests above pass even if lock() were a no-op. This one does not:
    // an unguarded counter reliably loses updates across four threads.
    const Ctx = struct {
        m: Mutex = .{},
        counter: u64 = 0,

        fn bump(self: *@This(), n: usize) void {
            var i: usize = 0;
            while (i < n) : (i += 1) {
                self.m.lock();
                defer self.m.unlock();
                self.counter += 1; // deliberately non-atomic
            }
        }
    };

    var ctx: Ctx = .{};
    const per_thread = 20_000;
    const thread_count = 4;
    var threads: [thread_count]std.Thread = undefined;
    for (&threads) |*t| t.* = try std.Thread.spawn(.{}, Ctx.bump, .{ &ctx, per_thread });
    for (threads) |t| t.join();

    try std.testing.expectEqual(@as(u64, thread_count * per_thread), ctx.counter);
}

/// Replaces the removed `std.Thread.RwLock`.
///
/// 0.16 took every synchronisation primitive out of `std.Thread`, RwLock
/// included. This tree uses it in one place -- the sharded basal-ganglia
/// tables -- with 16 shared-lock sites against a handful of exclusive ones, so
/// aliasing it to `Mutex` would be correct but would serialise every reader on
/// a hot path. Hence a real one.
///
/// Reader-preferring: a continuous stream of readers can starve a writer. That
/// is the right trade here (reads dominate, and every critical section is a few
/// map operations) and the wrong one for a write-heavy structure. Like `Mutex`
/// above, this spins rather than blocking, so it suits short sections only.
pub const RwLock = struct {
    /// High bit marks an exclusive holder; the low bits count shared holders.
    /// The two are mutually exclusive, so a non-zero state with the high bit
    /// clear means "readers present, no writer".
    state: std.atomic.Value(u32) = .init(0),

    const WRITER: u32 = 1 << 31;

    pub fn lock(self: *RwLock) void {
        while (true) {
            if (self.state.cmpxchgWeak(0, WRITER, .acquire, .monotonic) == null) return;
            std.atomic.spinLoopHint();
        }
    }

    pub fn unlock(self: *RwLock) void {
        self.state.store(0, .release);
    }

    pub fn tryLock(self: *RwLock) bool {
        return self.state.cmpxchgStrong(0, WRITER, .acquire, .monotonic) == null;
    }

    pub fn lockShared(self: *RwLock) void {
        while (true) {
            const s = self.state.load(.monotonic);
            if (s & WRITER == 0 and
                self.state.cmpxchgWeak(s, s + 1, .acquire, .monotonic) == null) return;
            std.atomic.spinLoopHint();
        }
    }

    pub fn unlockShared(self: *RwLock) void {
        _ = self.state.fetchSub(1, .release);
    }

    pub fn tryLockShared(self: *RwLock) bool {
        const s = self.state.load(.monotonic);
        if (s & WRITER != 0) return false;
        return self.state.cmpxchgStrong(s, s + 1, .acquire, .monotonic) == null;
    }
};

test "RwLock: readers share, a writer excludes" {
    var l: RwLock = .{};
    l.lockShared();
    try std.testing.expect(l.tryLockShared()); // a second reader gets in
    try std.testing.expect(!l.tryLock()); // but a writer does not
    l.unlockShared();
    l.unlockShared();
    try std.testing.expect(l.tryLock()); // free once all readers leave
    try std.testing.expect(!l.tryLockShared()); // and now readers are shut out
    l.unlock();
}

test "RwLock: exclusive sections do not interleave" {
    // Same shape as the Mutex contention test: this fails if lock() lets two
    // writers in at once.
    const Ctx = struct {
        l: RwLock = .{},
        counter: u64 = 0,
        fn bump(self: *@This(), n: usize) void {
            var i: usize = 0;
            while (i < n) : (i += 1) {
                self.l.lock();
                defer self.l.unlock();
                self.counter += 1;
            }
        }
    };
    var ctx: Ctx = .{};
    var threads: [4]std.Thread = undefined;
    for (&threads) |*t| t.* = try std.Thread.spawn(.{}, Ctx.bump, .{ &ctx, 20_000 });
    for (threads) |t| t.join();
    try std.testing.expectEqual(@as(u64, 80_000), ctx.counter);
}

test "RwLock: concurrent readers all observe a stable value" {
    const Ctx = struct {
        l: RwLock = .{},
        value: u64 = 42,
        ok: std.atomic.Value(u32) = .init(0),
        fn read(self: *@This(), n: usize) void {
            var i: usize = 0;
            while (i < n) : (i += 1) {
                self.l.lockShared();
                defer self.l.unlockShared();
                if (self.value == 42) _ = self.ok.fetchAdd(1, .monotonic);
            }
        }
    };
    var ctx: Ctx = .{};
    var threads: [4]std.Thread = undefined;
    for (&threads) |*t| t.* = try std.Thread.spawn(.{}, Ctx.read, .{ &ctx, 5_000 });
    for (threads) |t| t.join();
    try std.testing.expectEqual(@as(u32, 20_000), ctx.ok.load(.monotonic));
}
