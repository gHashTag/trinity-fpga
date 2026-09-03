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
