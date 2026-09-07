//! Does std.Io.Group actually behave the way the pipeline assumes?
//!
//! `runPipelineParallel` in rna_polymerase.zig replaced std.Thread.Pool +
//! WaitGroup with std.Io.Group and had never been executed. The collection
//! loop immediately after `group.await` reads every worker's context and
//! trusts it to be finished, so if await returns early the pipeline reports
//! results that were never written.
//!
//! The tests live here rather than beside the call site for a blunt reason:
//! rna_polymerase.zig is not reachable from the `test` step, so tests written
//! there do not run. Verified, not assumed -- an always-failing test added to
//! that file returned rc=0. What is tested here is the Io.Group CONTRACT the
//! call site depends on, in the same shape it uses.
//!
//! phi^2 + 1/phi^2 = 3 = TRINITY

const std = @import("std");
const tri_io = @import("tri_io");
const tri_time = @import("tri_time");

// ═══════════════════════════════════════════════════════════════════════════════
// Io.Group tests (#764)
// ═══════════════════════════════════════════════════════════════════════════════
//
// runPipelineParallel replaced std.Thread.Pool + WaitGroup with std.Io.Group,
// and had never been executed. The collection loop immediately after
// `group.await` reads every worker's context and trusts it to be finished --
// so if await returns early, the pipeline silently reports results that were
// never written. That is the failure this pins, using the same shape as the
// call site rather than a toy.

const GroupProbe = struct {
    /// Per-worker slot, exactly like ParallelLinkContext: the worker writes
    /// its own and nothing is shared.
    const Slot = struct {
        index: usize = 0,
        ran: bool = false,
        value: u64 = 0,
    };

    fn work(slot: *Slot) void {
        // Enough delay that a non-waiting `await` returns before these land.
        tri_time.sleep(20 * std.time.ns_per_ms);
        slot.value = @as(u64, slot.index) * 7 + 1;
        slot.ran = true;
    }
};

test "Io.Group.await waits for every worker before the collection loop reads" {
    const io = tri_io.get();

    var slots: [8]GroupProbe.Slot = undefined;
    for (&slots, 0..) |*s, i| s.* = .{ .index = i };

    var group: std.Io.Group = .init;
    defer group.cancel(io);
    for (&slots) |*s| group.async(io, GroupProbe.work, .{s});
    group.await(io) catch {};

    // The assertion that matters: EVERY slot is written by the time await
    // returns. With a pool that did not join, some of these are still false.
    for (&slots, 0..) |*s, i| {
        try std.testing.expect(s.ran);
        try std.testing.expectEqual(@as(u64, @as(u64, i) * 7 + 1), s.value);
    }
}

test "Io.Group runs the workers concurrently, not one after another" {
    // If the group serialised, eight 20ms sleeps would take ~160ms. This is
    // the property the migration was supposed to preserve -- a Group that
    // silently ran sequentially would pass the test above and still be a
    // regression.
    const io = tri_io.get();

    var slots: [8]GroupProbe.Slot = undefined;
    for (&slots, 0..) |*s, i| s.* = .{ .index = i };

    var timer = try tri_time.Timer.start();
    var group: std.Io.Group = .init;
    defer group.cancel(io);
    for (&slots) |*s| group.async(io, GroupProbe.work, .{s});
    group.await(io) catch {};
    const elapsed_ms = timer.read() / std.time.ns_per_ms;

    for (&slots) |*s| try std.testing.expect(s.ran);
    // Generous: serial would be ~160ms, concurrent ~20-40ms. 120 leaves room
    // for a loaded machine without admitting a serial run.
    try std.testing.expect(elapsed_ms < 120);
}

test "an empty Io.Group awaits immediately rather than hanging" {
    // active_count can be zero on the call-site's path. A Group with no tasks
    // must not block -- its token is null and await returns at once.
    const io = tri_io.get();
    var group: std.Io.Group = .init;
    defer group.cancel(io);

    var timer = try tri_time.Timer.start();
    group.await(io) catch {};
    try std.testing.expect(timer.read() / std.time.ns_per_ms < 50);
}
