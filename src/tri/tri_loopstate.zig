// tri loop-state — read and advance the autonomous loop's STATE.json.
//
// The loop fires every 15 minutes from cron. Each firing must know, without
// re-deriving it, what is already finished; otherwise a later iteration redoes
// or undoes an earlier one. STATE.json is that memory, and these subcommands
// are the only sanctioned way to move an item, so the invariant "never redo a
// done item" lives in code rather than in a habit.
//
// Deliberately dependency-free: this file must stay compilable and testable on
// its own (`zig test src/tri/tri_loopstate.zig`) even while the rest of the CLI
// is blocked on unrelated API work.
//
// Dmitrii Vasilev / @gHashTag

const std = @import("std");

pub const default_state_path = ".trinity/loop/STATE.json";
pub const default_journal_path = ".trinity/loop/JOURNAL.md";

pub const Error = error{
    StateNotFound,
    MalformedState,
    ItemNotFound,
    AlreadyDone,
};

/// One backlog row, as the loop sees it.
pub const Item = struct {
    id: []const u8,
    prio: i64 = 0,
    what: []const u8,
    status: []const u8 = "pending",
    blocked: bool = false,
};

/// A parsed view over STATE.json. Borrows from `doc`; keep `doc` alive.
pub const State = struct {
    doc: std.json.Parsed(std.json.Value),
    iteration: i64,
    done_count: usize,

    pub fn deinit(self: *State) void {
        self.doc.deinit();
    }

    pub fn root(self: *const State) std.json.Value {
        return self.doc.value;
    }
};

/// Parse STATE.json from raw bytes.
pub fn parse(allocator: std.mem.Allocator, bytes: []const u8) !State {
    const doc = std.json.parseFromSlice(std.json.Value, allocator, bytes, .{}) catch
        return Error.MalformedState;
    errdefer doc.deinit();

    const obj = switch (doc.value) {
        .object => |o| o,
        else => return Error.MalformedState,
    };

    const loop = obj.get("loop") orelse return Error.MalformedState;
    const iter_val = switch (loop) {
        .object => |o| o.get("iteration") orelse return Error.MalformedState,
        else => return Error.MalformedState,
    };
    const iteration = switch (iter_val) {
        .integer => |i| i,
        else => return Error.MalformedState,
    };

    const done_count = blk: {
        const d = obj.get("done") orelse break :blk 0;
        break :blk switch (d) {
            .array => |a| a.items.len,
            else => 0,
        };
    };

    return .{ .doc = doc, .iteration = iteration, .done_count = done_count };
}

fn strField(obj: std.json.ObjectMap, key: []const u8, fallback: []const u8) []const u8 {
    const v = obj.get(key) orelse return fallback;
    return switch (v) {
        .string => |s| s,
        else => fallback,
    };
}

/// The next actionable item: lowest `prio` among pending rows whose
/// `blocked_by` list is empty. Returns null when the backlog is exhausted or
/// everything left is blocked -- the caller must tell those two apart before
/// reporting "nothing to do".
pub fn nextItem(allocator: std.mem.Allocator, st: *const State) !?Item {
    _ = allocator;
    const obj = switch (st.root()) {
        .object => |o| o,
        else => return Error.MalformedState,
    };
    const backlog = obj.get("backlog") orelse return null;
    const rows = switch (backlog) {
        .array => |a| a.items,
        else => return Error.MalformedState,
    };

    var best: ?Item = null;
    for (rows) |row| {
        const r = switch (row) {
            .object => |o| o,
            else => continue,
        };
        const status = strField(r, "status", "pending");
        if (std.mem.eql(u8, status, "completed")) continue;

        var blocked = false;
        if (r.get("blocked_by")) |bb| {
            switch (bb) {
                .array => |a| blocked = a.items.len > 0,
                else => {},
            }
        }
        if (blocked) continue;

        const prio: i64 = switch (r.get("prio") orelse std.json.Value{ .integer = 999 }) {
            .integer => |i| i,
            else => 999,
        };
        const cand = Item{
            .id = strField(r, "id", "?"),
            .prio = prio,
            .what = strField(r, "what", ""),
            .status = status,
            .blocked = false,
        };
        if (best == null or prio < best.?.prio) best = cand;
    }
    return best;
}

/// True when `id` is already recorded in `done`. The loop calls this before
/// starting anything, so a re-fired cron cannot repeat finished work.
pub fn isDone(st: *const State, id: []const u8) bool {
    const obj = switch (st.root()) {
        .object => |o| o,
        else => return false,
    };
    const done = obj.get("done") orelse return false;
    const rows = switch (done) {
        .array => |a| a.items,
        else => return false,
    };
    for (rows) |row| {
        const r = switch (row) {
            .object => |o| o,
            else => continue,
        };
        if (std.mem.eql(u8, strField(r, "id", ""), id)) return true;
    }
    return false;
}

/// Counts recomputed directly from STATE.json, independent of whatever any
/// other file (the dashboard) currently claims.
pub const LiveCounts = struct {
    backlog_total: usize = 0,
    backlog_open: usize = 0,
    anomalies_total: usize = 0,
    anomalies_open: usize = 0,
    done_count: usize = 0,
};

/// A backlog row counts as open unless its status is exactly "completed".
/// An anomaly counts as open when its `status` field is absent, empty, or
/// JSON null -- the same convention STATE.json's own anomaly rows already use.
pub fn liveCounts(st: *const State) LiveCounts {
    var out = LiveCounts{ .done_count = st.done_count };
    const obj = switch (st.root()) {
        .object => |o| o,
        else => return out,
    };

    if (obj.get("backlog")) |backlog| if (backlog == .array) {
        for (backlog.array.items) |row| {
            if (row != .object) continue;
            out.backlog_total += 1;
            const status = strField(row.object, "status", "pending");
            if (!std.mem.eql(u8, status, "completed")) out.backlog_open += 1;
        }
    };

    if (obj.get("anomalies")) |anomalies| if (anomalies == .array) {
        for (anomalies.array.items) |row| {
            if (row != .object) continue;
            out.anomalies_total += 1;
            const status = strField(row.object, "status", "");
            if (status.len == 0) out.anomalies_open += 1;
        }
    };

    return out;
}

/// Scan a dashboard.html readout block for the integer shown next to `label`,
/// following the fixed `<div class="n">N</div><div class="l">label</div>`
/// shape this project's dashboard already uses. Returns null when the label
/// is absent or the preceding number cell isn't a plain integer (e.g. "1/4"),
/// rather than guessing.
pub fn extractReadoutNumber(html: []const u8, label: []const u8) ?i64 {
    const label_tag = "<div class=\"l\">";
    const label_idx = std.mem.indexOf(u8, html, label) orelse return null;
    const tag_idx = std.mem.lastIndexOf(u8, html[0..label_idx], label_tag) orelse return null;

    const num_tag = "<div class=\"n\">";
    const num_start = std.mem.lastIndexOf(u8, html[0..tag_idx], num_tag) orelse return null;
    const digits_start = num_start + num_tag.len;
    const digits_end = std.mem.indexOfScalarPos(u8, html, digits_start, '<') orelse return null;

    return std.fmt.parseInt(i64, html[digits_start..digits_end], 10) catch null;
}

/// Diff live STATE.json counts against whatever a dashboard's readout block
/// currently claims for "backlog open" and "anomalies open". Caller owns the
/// returned slice. This is the mechanical form of the check an external audit
/// otherwise has to perform by hand.
pub fn checkDrift(allocator: std.mem.Allocator, live: LiveCounts, dashboard_html: []const u8) ![]u8 {
    var out: std.ArrayList(u8) = .empty;
    errdefer out.deinit(allocator);

    const checks = [_]struct { label: []const u8, live_value: usize }{
        .{ .label = "backlog open", .live_value = live.backlog_open },
        .{ .label = "anomalies open", .live_value = live.anomalies_open },
    };

    var drift_found = false;
    for (checks) |c| {
        const claimed = extractReadoutNumber(dashboard_html, c.label);
        if (claimed) |claim| {
            if (claim == @as(i64, @intCast(c.live_value))) {
                try out.print(allocator, "ok      {s}: {d}\n", .{ c.label, c.live_value });
            } else {
                drift_found = true;
                try out.print(allocator, "DRIFT   {s}: dashboard claims {d}, live STATE.json says {d}\n", .{ c.label, claim, c.live_value });
            }
        } else {
            drift_found = true;
            try out.print(allocator, "MISSING {s}: dashboard has no readable number for this label (live: {d})\n", .{ c.label, c.live_value });
        }
    }
    if (!drift_found) try out.print(allocator, "checked, consistent\n", .{});

    return out.toOwnedSlice(allocator);
}

/// Render a one-screen status line set. Caller owns the returned slice.
pub fn renderStatus(allocator: std.mem.Allocator, st: *const State) ![]u8 {
    const head = try std.fmt.allocPrint(
        allocator,
        "iteration {d}  ·  {d} done\n",
        .{ st.iteration, st.done_count },
    );
    defer allocator.free(head);

    const tail = if (try nextItem(allocator, st)) |it|
        try std.fmt.allocPrint(
            allocator,
            "next: {s} (prio {d}) {s}\n",
            .{ it.id, it.prio, it.what },
        )
    else
        try allocator.dupe(u8, "next: none actionable (backlog empty or everything blocked)\n");
    defer allocator.free(tail);

    return std.mem.concat(allocator, u8, &.{ head, tail });
}

// ---------------------------------------------------------------------------

const test_state =
    \\{
    \\  "loop": {"id":"t","iteration":7},
    \\  "done": [{"id":"D1","what":"a"},{"id":"D2","what":"b"}],
    \\  "backlog": [
    \\    {"id":"B3","prio":3,"what":"third","blocked_by":[],"status":"pending"},
    \\    {"id":"B1","prio":1,"what":"first","blocked_by":["B9"],"status":"pending"},
    \\    {"id":"B2","prio":2,"what":"second","blocked_by":[],"status":"pending"}
    \\  ]
    \\}
;

test "parse reads iteration and done count" {
    var st = try parse(std.testing.allocator, test_state);
    defer st.deinit();
    try std.testing.expectEqual(@as(i64, 7), st.iteration);
    try std.testing.expectEqual(@as(usize, 2), st.done_count);
}

test "nextItem skips blocked rows even when they rank first" {
    var st = try parse(std.testing.allocator, test_state);
    defer st.deinit();
    const it = (try nextItem(std.testing.allocator, &st)).?;
    // B1 has prio 1 but is blocked by B9, so B2 wins.
    try std.testing.expectEqualStrings("B2", it.id);
}

test "nextItem returns null when nothing is actionable" {
    const blocked_only =
        \\{"loop":{"iteration":1},"done":[],
        \\ "backlog":[{"id":"B1","prio":1,"what":"x","blocked_by":["B2"],"status":"pending"}]}
    ;
    var st = try parse(std.testing.allocator, blocked_only);
    defer st.deinit();
    try std.testing.expect((try nextItem(std.testing.allocator, &st)) == null);
}

test "nextItem skips completed rows" {
    const one_done =
        \\{"loop":{"iteration":1},"done":[],
        \\ "backlog":[{"id":"B1","prio":1,"what":"x","blocked_by":[],"status":"completed"},
        \\            {"id":"B2","prio":5,"what":"y","blocked_by":[],"status":"pending"}]}
    ;
    var st = try parse(std.testing.allocator, one_done);
    defer st.deinit();
    const it = (try nextItem(std.testing.allocator, &st)).?;
    try std.testing.expectEqualStrings("B2", it.id);
}

test "isDone guards against redoing finished work" {
    var st = try parse(std.testing.allocator, test_state);
    defer st.deinit();
    try std.testing.expect(isDone(&st, "D1"));
    try std.testing.expect(isDone(&st, "D2"));
    try std.testing.expect(!isDone(&st, "B2"));
    try std.testing.expect(!isDone(&st, ""));
}

test "malformed state is an error, not a silent default" {
    try std.testing.expectError(Error.MalformedState, parse(std.testing.allocator, "{ not json"));
    try std.testing.expectError(Error.MalformedState, parse(std.testing.allocator, "[]"));
    // A state with no loop.iteration must fail loudly: a loop that cannot tell
    // which iteration it is on would happily repeat one.
    try std.testing.expectError(Error.MalformedState, parse(std.testing.allocator, "{\"loop\":{}}"));
}

test "renderStatus names the next item" {
    var st = try parse(std.testing.allocator, test_state);
    defer st.deinit();
    const s = try renderStatus(std.testing.allocator, &st);
    defer std.testing.allocator.free(s);
    try std.testing.expect(std.mem.indexOf(u8, s, "iteration 7") != null);
    try std.testing.expect(std.mem.indexOf(u8, s, "B2") != null);
}

test "liveCounts treats only completed backlog rows as closed" {
    var st = try parse(std.testing.allocator, test_state);
    defer st.deinit();
    const c = liveCounts(&st);
    try std.testing.expectEqual(@as(usize, 3), c.backlog_total);
    try std.testing.expectEqual(@as(usize, 3), c.backlog_open); // none marked "completed" in test_state
    try std.testing.expectEqual(@as(usize, 2), c.done_count);
}

test "liveCounts treats a missing or empty anomaly status as open" {
    const with_anomalies =
        \\{"loop":{"iteration":1},"done":[],"backlog":[],
        \\ "anomalies":[{"id":"A1","status":"resolved"},{"id":"A2"},{"id":"A3","status":""}]}
    ;
    var st = try parse(std.testing.allocator, with_anomalies);
    defer st.deinit();
    const c = liveCounts(&st);
    try std.testing.expectEqual(@as(usize, 3), c.anomalies_total);
    try std.testing.expectEqual(@as(usize, 2), c.anomalies_open);
}

const test_readout =
    \\<div class="readout">
    \\  <div class="cellstat"><div class="n">8</div><div class="l">backlog open</div></div>
    \\  <div class="cellstat"><div class="n">1</div><div class="l">anomalies open</div></div>
    \\  <div class="cellstat"><div class="n">1/4</div><div class="l">rows on silicon</div></div>
    \\</div>
;

test "extractReadoutNumber reads the number preceding a label" {
    try std.testing.expectEqual(@as(?i64, 8), extractReadoutNumber(test_readout, "backlog open"));
    try std.testing.expectEqual(@as(?i64, 1), extractReadoutNumber(test_readout, "anomalies open"));
}

test "extractReadoutNumber returns null for a non-integer cell or missing label" {
    try std.testing.expectEqual(@as(?i64, null), extractReadoutNumber(test_readout, "rows on silicon"));
    try std.testing.expectEqual(@as(?i64, null), extractReadoutNumber(test_readout, "nonexistent label"));
}

test "checkDrift reports a mismatch against a stale dashboard" {
    const live = LiveCounts{ .backlog_open = 6, .anomalies_open = 5 };
    const report = try checkDrift(std.testing.allocator, live, test_readout);
    defer std.testing.allocator.free(report);
    try std.testing.expect(std.mem.indexOf(u8, report, "DRIFT   backlog open: dashboard claims 8, live STATE.json says 6") != null);
    try std.testing.expect(std.mem.indexOf(u8, report, "DRIFT   anomalies open: dashboard claims 1, live STATE.json says 5") != null);
}

test "checkDrift reports consistency when numbers match" {
    const live = LiveCounts{ .backlog_open = 8, .anomalies_open = 1 };
    const report = try checkDrift(std.testing.allocator, live, test_readout);
    defer std.testing.allocator.free(report);
    try std.testing.expect(std.mem.indexOf(u8, report, "checked, consistent") != null);
}
