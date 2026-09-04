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

fn boolField(obj: std.json.ObjectMap, key: []const u8, fallback: bool) bool {
    const v = obj.get(key) orelse return fallback;
    return switch (v) {
        .bool => |b| b,
        else => fallback,
    };
}

fn isGated(row: std.json.ObjectMap) bool {
    return boolField(row, "needs_operator_decision", false);
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

        // A row waiting on a human judgment call is skipped exactly like a
        // row blocked by another backlog item -- it is a normal, expected,
        // knowable-in-advance reason nextItem() can't return it, not a
        // failure. It never starves unrelated, doable work. See
        // decisionGateStatus() for the separate "is EVERYTHING gated" check.
        if (isGated(r)) continue;

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

pub const DecisionGateStatus = enum { clear, some_gated, all_gated };

pub const DecisionGate = struct {
    status: DecisionGateStatus,
    /// ids of every open, unblocked, needs_operator_decision row -- populated
    /// whenever any exist, regardless of `status` (so a caller can log
    /// "gated but not blocking" as well as "blocking").
    gated_ids: std.ArrayList([]const u8),

    pub fn deinit(self: *DecisionGate, allocator: std.mem.Allocator) void {
        self.gated_ids.deinit(allocator);
    }
};

/// Distinguishes three states nextItem() alone cannot tell apart once it
/// skips gated rows: `clear` (no candidates at all -- plain backlog
/// exhaustion, not alarming), `some_gated` (at least one candidate is
/// actionable right now; any gated rows are merely visible, not blocking),
/// and `all_gated` (every remaining candidate needs an operator decision --
/// the real tripwire: nothing else is actionable, by construction, so this
/// is the only case worth halting for). Caller owns the returned gated_ids.
pub fn decisionGateStatus(allocator: std.mem.Allocator, st: *const State) !DecisionGate {
    const obj = switch (st.root()) {
        .object => |o| o,
        else => return Error.MalformedState,
    };
    var gated_ids: std.ArrayList([]const u8) = .empty;
    errdefer gated_ids.deinit(allocator);

    const backlog = obj.get("backlog") orelse return .{ .status = .clear, .gated_ids = gated_ids };
    const rows = switch (backlog) {
        .array => |a| a.items,
        else => return Error.MalformedState,
    };

    var candidates: usize = 0;
    for (rows) |row| {
        const r = switch (row) {
            .object => |o| o,
            else => continue,
        };
        if (std.mem.eql(u8, strField(r, "status", "pending"), "completed")) continue;
        var blocked = false;
        if (r.get("blocked_by")) |bb| switch (bb) {
            .array => |a| blocked = a.items.len > 0,
            else => {},
        };
        if (blocked) continue;

        candidates += 1;
        if (isGated(r)) try gated_ids.append(allocator, strField(r, "id", "?"));
    }

    const status: DecisionGateStatus = if (candidates == 0)
        .clear
    else if (gated_ids.items.len == candidates)
        .all_gated
    else
        .some_gated;

    return .{ .status = status, .gated_ids = gated_ids };
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

const readout_block_anchor = "<div class=\"readout\">";

/// Locates the digit span for `label`'s number cell, scoped to start no
/// earlier than `<div class="readout">` -- NOT a whole-document search.
/// Whole-document search is a real bug, not a hypothetical one: this file's
/// own halt banner sits ABOVE the readout block and can echo a label's exact
/// words in its own diagnostic text (e.g. "MISSING backlog open: ..."),
/// which a document-wide `indexOf` would match instead of the real cell --
/// discovered by running this against the live dashboard, not by reasoning
/// about it. Returns null if the readout block itself, the label, or its
/// preceding `<div class="n">...</div>` cell can't be found.
fn findReadoutDigits(html: []const u8, label: []const u8) ?struct { start: usize, end: usize } {
    const block_start = std.mem.indexOf(u8, html, readout_block_anchor) orelse return null;
    const scope = html[block_start..];

    const label_tag = "<div class=\"l\">";
    const label_idx = std.mem.indexOf(u8, scope, label) orelse return null;
    const tag_idx = std.mem.lastIndexOf(u8, scope[0..label_idx], label_tag) orelse return null;

    const num_tag = "<div class=\"n\">";
    const num_start = std.mem.lastIndexOf(u8, scope[0..tag_idx], num_tag) orelse return null;
    const digits_start = num_start + num_tag.len;
    const digits_end = std.mem.indexOfScalarPos(u8, scope, digits_start, '<') orelse return null;

    return .{ .start = block_start + digits_start, .end = block_start + digits_end };
}

/// Scan a dashboard.html readout block for the integer shown next to `label`,
/// following the fixed `<div class="n">N</div><div class="l">label</div>`
/// shape this project's dashboard already uses. Returns null when the label
/// is absent or the preceding number cell isn't a plain integer (e.g. "1/4"),
/// rather than guessing.
pub fn extractReadoutNumber(html: []const u8, label: []const u8) ?i64 {
    const digits = findReadoutDigits(html, label) orelse return null;
    return std.fmt.parseInt(i64, html[digits.start..digits.end], 10) catch null;
}

/// Rewrite the number cell preceding `label` (same shape `extractReadoutNumber`
/// reads) to `new_value`. Errors -- never silently no-ops -- when the label or
/// its preceding `<div class="n">...</div>` cell can't be found, matching
/// `extractReadoutNumber`'s own "don't guess" contract. Caller owns the
/// returned slice.
pub fn rewriteReadoutNumber(allocator: std.mem.Allocator, html: []const u8, label: []const u8, new_value: i64) ![]u8 {
    const digits = findReadoutDigits(html, label) orelse return Error.MalformedState;

    var out: std.ArrayList(u8) = .empty;
    errdefer out.deinit(allocator);
    try out.appendSlice(allocator, html[0..digits.start]);
    try out.print(allocator, "{d}", .{new_value});
    try out.appendSlice(allocator, html[digits.end..]);
    return out.toOwnedSlice(allocator);
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

pub const HealResult = struct {
    /// Caller owns; may be identical content to the input if nothing needed
    /// fixing.
    healed_html: []u8,
    /// checkDrift()'s report AFTER the heal attempt. If this still contains
    /// "DRIFT" or "MISSING", the heal did not fully succeed (a label's cell
    /// is missing/unparseable) and it needs a human, not another attempt.
    final_report: []u8,

    pub fn deinit(self: *HealResult, allocator: std.mem.Allocator) void {
        allocator.free(self.healed_html);
        allocator.free(self.final_report);
    }
};

/// A plain numeric readout mismatch is fully mechanical and safe to fix
/// every time it's found -- both inputs (the live counts just computed, and
/// the dashboard file about to be rewritten) are entirely under the loop's
/// own control, so there is no guessing involved. Attempts both known labels
/// unconditionally (idempotent: rewriting an already-correct number is a
/// no-op edit); a label whose cell can't be found at all (MISSING) is left
/// untouched -- guessing at broken HTML structure risks making it worse.
/// Caller owns the returned HealResult.
pub fn autoHealDrift(allocator: std.mem.Allocator, live: LiveCounts, dashboard_html: []const u8) !HealResult {
    const fixes = [_]struct { label: []const u8, value: usize }{
        .{ .label = "backlog open", .value = live.backlog_open },
        .{ .label = "anomalies open", .value = live.anomalies_open },
    };

    var current = try allocator.dupe(u8, dashboard_html);
    for (fixes) |f| {
        const attempt = rewriteReadoutNumber(allocator, current, f.label, @intCast(f.value)) catch continue;
        allocator.free(current);
        current = attempt;
    }

    const final_report = try checkDrift(allocator, live, current);
    return .{ .healed_html = current, .final_report = final_report };
}

// --- Tripwires: disk / drift / decision-gridlock, all recomputed fresh --------
//
// Every tripwire below is evaluated ONLY from a fresh reading taken this
// call -- never from a value a previous run wrote to STATE.json. This is
// deliberate: this project already found one stale self-belief about its
// own live state (a cron job ID that had died with a prior session, still
// cited as current). A halt/resume decision that trusted its own prior
// verdict would be the same failure shape applied to safety-critical state.
// Thresholds are given as parameters, not hardcoded, so the operator can
// retune them by editing STATE.json's loop.tripwires block, matching this
// project's spec-first convention.

pub const DiskThresholds = struct {
    halt_gib: f64 = 2.0,
    warn_gib: f64 = 5.0,
    resume_gib: f64 = 4.0,
};

pub const DiskTier = enum { full, warn, halt };

/// Pure, three-tier classification -- injectable free_gib so this is testable
/// without a real filesystem call. See `freeGiB` for the real reading.
pub fn evalDiskTier(free_gib: f64, t: DiskThresholds) DiskTier {
    if (free_gib < t.halt_gib) return .halt;
    if (free_gib < t.warn_gib) return .warn;
    return .full;
}

fn floatField(obj: std.json.ObjectMap, key: []const u8, fallback: f64) f64 {
    const v = obj.get(key) orelse return fallback;
    return switch (v) {
        .float => |f| f,
        .integer => |i| @floatFromInt(i),
        else => fallback,
    };
}

/// Reads loop.tripwires.{disk_halt_free_gib,disk_warn_free_gib,disk_resume_free_gib}
/// from STATE.json, falling back to DiskThresholds{}'s defaults per-field when
/// absent -- so an operator can retune one number in STATE.json (this
/// project's spec-first convention) without needing all three present.
pub fn readDiskThresholds(st: *const State) DiskThresholds {
    const d = DiskThresholds{};
    const obj = switch (st.root()) {
        .object => |o| o,
        else => return d,
    };
    const loop = switch (obj.get("loop") orelse return d) {
        .object => |o| o,
        else => return d,
    };
    const tw = switch (loop.get("tripwires") orelse return d) {
        .object => |o| o,
        else => return d,
    };
    return .{
        .halt_gib = floatField(tw, "disk_halt_free_gib", d.halt_gib),
        .warn_gib = floatField(tw, "disk_warn_free_gib", d.warn_gib),
        .resume_gib = floatField(tw, "disk_resume_free_gib", d.resume_gib),
    };
}

const builtin = @import("builtin");

const DarwinStatvfs = extern struct {
    f_bsize: c_ulong,
    f_frsize: c_ulong,
    f_blocks: c_uint,
    f_bfree: c_uint,
    f_bavail: c_uint,
    f_files: c_uint,
    f_ffree: c_uint,
    f_favail: c_uint,
    f_fsid: c_ulong,
    f_flag: c_ulong,
    f_namemax: c_ulong,
};
extern "c" fn statvfs(path: [*:0]const u8, buf: *DarwinStatvfs) c_int;

/// Free space on the filesystem containing `path`, in GiB. A direct libc
/// `statvfs` binding -- no shell subprocess, per this project's no-shell-
/// scripts rule; verified against the real struct layout in the macOS SDK
/// header (sys/statvfs.h) and cross-checked against `df -h` output, not
/// assumed from a remembered ABI.
pub fn freeGiB(path: [*:0]const u8) !f64 {
    if (builtin.os.tag != .macos) return error.UnsupportedPlatform;
    var buf: DarwinStatvfs = undefined;
    if (statvfs(path, &buf) != 0) return error.StatvfsFailed;
    const free_bytes: u64 = @as(u64, buf.f_bavail) * @as(u64, buf.f_frsize);
    return @as(f64, @floatFromInt(free_bytes)) / (1024.0 * 1024.0 * 1024.0);
}

pub const TripwireReasons = struct {
    disk: bool = false,
    drift: bool = false,
    decision: bool = false,

    pub fn any(self: TripwireReasons) bool {
        return self.disk or self.drift or self.decision;
    }
};

/// Combine the three fresh readings into one verdict. Does not itself read
/// any file or take any measurement -- callers gather disk_tier (from
/// `evalDiskTier(freeGiB(...), ...)`), drift_report (from `checkDrift`), and
/// gate (from `decisionGateStatus`) first, so each input stays independently
/// testable and this function stays a pure combinator.
pub fn evaluateTripwires(disk_tier: DiskTier, drift_report: []const u8, gate_status: DecisionGateStatus) TripwireReasons {
    return .{
        .disk = disk_tier == .halt,
        .drift = std.mem.indexOf(u8, drift_report, "DRIFT") != null or std.mem.indexOf(u8, drift_report, "MISSING") != null,
        .decision = gate_status == .all_gated,
    };
}

const halt_banner_start = "<!-- LOOP_HALT_BANNER_START -->";
const halt_banner_end = "<!-- LOOP_HALT_BANNER_END -->";

/// Render the banner shown at the top of dashboard.html when halted. Empty
/// string when `reasons.any()` is false -- the caller always calls this and
/// always calls `injectHaltBanner`, so a clear state actively erases a stale
/// banner rather than merely not adding a new one.
pub fn renderHaltBanner(allocator: std.mem.Allocator, reasons: TripwireReasons, detail: []const u8) ![]u8 {
    if (!reasons.any()) return allocator.dupe(u8, "");
    var names: std.ArrayList(u8) = .empty;
    defer names.deinit(allocator);
    if (reasons.disk) try names.print(allocator, "disk ", .{});
    if (reasons.drift) try names.print(allocator, "drift ", .{});
    if (reasons.decision) try names.print(allocator, "decision ", .{});
    return std.fmt.allocPrint(
        allocator,
        "<div class=\"halt-banner\" style=\"background:var(--bad);color:var(--paper);padding:.9rem 1.1rem;border-radius:2px;font-weight:650\">HALTED: {s}&mdash; {s}</div>",
        .{ names.items, detail },
    );
}

/// Replace whatever sits between the two banner markers in `html` with
/// `banner_html` (which may be empty). The markers themselves are preserved,
/// so this is idempotent across repeated calls and never depends on the
/// previous banner's content. Errors if the markers are missing entirely
/// (dashboard.html's structure changed) rather than silently no-op-ing.
pub fn injectHaltBanner(allocator: std.mem.Allocator, html: []const u8, banner_html: []const u8) ![]u8 {
    const start = std.mem.indexOf(u8, html, halt_banner_start) orelse return Error.MalformedState;
    const content_start = start + halt_banner_start.len;
    const end = std.mem.indexOfPos(u8, html, content_start, halt_banner_end) orelse return Error.MalformedState;

    var out: std.ArrayList(u8) = .empty;
    errdefer out.deinit(allocator);
    try out.appendSlice(allocator, html[0..content_start]);
    try out.appendSlice(allocator, banner_html);
    try out.appendSlice(allocator, html[end..]);
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

test "extractReadoutNumber is not fooled by the label's own words appearing before the readout block" {
    // Regression test for a real bug found by running this against the live
    // dashboard: a halt banner sitting ABOVE the readout block echoed
    // "backlog open" in its own diagnostic prose (e.g. "MISSING backlog
    // open: ..."), and a whole-document indexOf matched that plain-text
    // occurrence instead of the real <div class="l">backlog open</div> cell
    // -- returning null (MISSING) even though the real number was intact.
    const with_banner_prose = "<div class=\"halt-banner\">MISSING backlog open: no readable number</div>\n" ++ test_readout;
    try std.testing.expectEqual(@as(?i64, 8), extractReadoutNumber(with_banner_prose, "backlog open"));
    try std.testing.expectEqual(@as(?i64, 1), extractReadoutNumber(with_banner_prose, "anomalies open"));
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

test "rewriteReadoutNumber replaces only the targeted cell" {
    const rewritten = try rewriteReadoutNumber(std.testing.allocator, test_readout, "backlog open", 6);
    defer std.testing.allocator.free(rewritten);
    try std.testing.expectEqual(@as(?i64, 6), extractReadoutNumber(rewritten, "backlog open"));
    try std.testing.expectEqual(@as(?i64, 1), extractReadoutNumber(rewritten, "anomalies open")); // untouched
}

test "rewriteReadoutNumber errors on a label it can't find" {
    try std.testing.expectError(Error.MalformedState, rewriteReadoutNumber(std.testing.allocator, test_readout, "nonexistent label", 6));
}

test "autoHealDrift fixes a plain numeric mismatch and reports consistent" {
    const live = LiveCounts{ .backlog_open = 6, .anomalies_open = 5 };
    var heal = try autoHealDrift(std.testing.allocator, live, test_readout);
    defer heal.deinit(std.testing.allocator);
    try std.testing.expect(std.mem.indexOf(u8, heal.final_report, "checked, consistent") != null);
    try std.testing.expectEqual(@as(?i64, 6), extractReadoutNumber(heal.healed_html, "backlog open"));
    try std.testing.expectEqual(@as(?i64, 5), extractReadoutNumber(heal.healed_html, "anomalies open"));
}

test "autoHealDrift is a no-op when nothing was wrong" {
    const live = LiveCounts{ .backlog_open = 8, .anomalies_open = 1 };
    var heal = try autoHealDrift(std.testing.allocator, live, test_readout);
    defer heal.deinit(std.testing.allocator);
    try std.testing.expectEqualStrings(test_readout, heal.healed_html);
    try std.testing.expect(std.mem.indexOf(u8, heal.final_report, "checked, consistent") != null);
}

test "autoHealDrift leaves a MISSING label alone rather than guessing" {
    const missing_readout =
        \\<div class="readout">
        \\  <div class="cellstat"><div class="n">8</div><div class="l">backlog open</div></div>
        \\</div>
    ;
    const live = LiveCounts{ .backlog_open = 6, .anomalies_open = 5 };
    var heal = try autoHealDrift(std.testing.allocator, live, missing_readout);
    defer heal.deinit(std.testing.allocator);
    try std.testing.expectEqual(@as(?i64, 6), extractReadoutNumber(heal.healed_html, "backlog open")); // this one healed
    try std.testing.expect(std.mem.indexOf(u8, heal.final_report, "MISSING anomalies open") != null); // this one can't
}

test "nextItem skips a needs_operator_decision row even when it ranks first" {
    const with_gate =
        \\{"loop":{"iteration":1},"done":[],
        \\ "backlog":[{"id":"B1","prio":1,"what":"gated","blocked_by":[],"status":"pending","needs_operator_decision":true},
        \\            {"id":"B2","prio":5,"what":"ungated","blocked_by":[],"status":"pending"}]}
    ;
    var st = try parse(std.testing.allocator, with_gate);
    defer st.deinit();
    const it = (try nextItem(std.testing.allocator, &st)).?;
    try std.testing.expectEqualStrings("B2", it.id);
}

test "decisionGateStatus reports clear when the backlog is empty of candidates" {
    var st = try parse(std.testing.allocator, "{\"loop\":{\"iteration\":1},\"done\":[],\"backlog\":[]}");
    defer st.deinit();
    var gate = try decisionGateStatus(std.testing.allocator, &st);
    defer gate.deinit(std.testing.allocator);
    try std.testing.expectEqual(DecisionGateStatus.clear, gate.status);
    try std.testing.expectEqual(@as(usize, 0), gate.gated_ids.items.len);
}

test "decisionGateStatus reports some_gated when unrelated work is still actionable" {
    const mixed =
        \\{"loop":{"iteration":1},"done":[],
        \\ "backlog":[{"id":"B18","prio":12,"what":"x","blocked_by":[],"status":"pending","needs_operator_decision":true},
        \\            {"id":"B17","prio":11,"what":"y","blocked_by":[],"status":"pending"}]}
    ;
    var st = try parse(std.testing.allocator, mixed);
    defer st.deinit();
    var gate = try decisionGateStatus(std.testing.allocator, &st);
    defer gate.deinit(std.testing.allocator);
    try std.testing.expectEqual(DecisionGateStatus.some_gated, gate.status);
    try std.testing.expectEqual(@as(usize, 1), gate.gated_ids.items.len);
    try std.testing.expectEqualStrings("B18", gate.gated_ids.items[0]);
}

test "decisionGateStatus reports all_gated only when every actionable row needs a decision" {
    const all_gated =
        \\{"loop":{"iteration":1},"done":[],
        \\ "backlog":[{"id":"B18","prio":12,"what":"x","blocked_by":[],"status":"pending","needs_operator_decision":true},
        \\            {"id":"B19","prio":13,"what":"y","blocked_by":[],"status":"pending","needs_operator_decision":true},
        \\            {"id":"B0","prio":1,"what":"z","blocked_by":[],"status":"completed"}]}
    ;
    var st = try parse(std.testing.allocator, all_gated);
    defer st.deinit();
    var gate = try decisionGateStatus(std.testing.allocator, &st);
    defer gate.deinit(std.testing.allocator);
    try std.testing.expectEqual(DecisionGateStatus.all_gated, gate.status);
    try std.testing.expectEqual(@as(usize, 2), gate.gated_ids.items.len);
}

test "evalDiskTier classifies against the three configured bands" {
    const t = DiskThresholds{};
    try std.testing.expectEqual(DiskTier.halt, evalDiskTier(1.5, t));
    try std.testing.expectEqual(DiskTier.warn, evalDiskTier(3.0, t));
    try std.testing.expectEqual(DiskTier.full, evalDiskTier(9.8, t));
    // boundaries are exclusive on the low side of each band
    try std.testing.expectEqual(DiskTier.warn, evalDiskTier(2.0, t));
    try std.testing.expectEqual(DiskTier.full, evalDiskTier(5.0, t));
}

test "readDiskThresholds falls back per-field when loop.tripwires is partial or absent" {
    var default_st = try parse(std.testing.allocator, test_state);
    defer default_st.deinit();
    const d = readDiskThresholds(&default_st);
    try std.testing.expectEqual(@as(f64, 2.0), d.halt_gib);
    try std.testing.expectEqual(@as(f64, 5.0), d.warn_gib);
    try std.testing.expectEqual(@as(f64, 4.0), d.resume_gib);

    const partial =
        \\{"loop":{"iteration":1,"tripwires":{"disk_halt_free_gib":3.5}},"done":[],"backlog":[]}
    ;
    var st = try parse(std.testing.allocator, partial);
    defer st.deinit();
    const p = readDiskThresholds(&st);
    try std.testing.expectEqual(@as(f64, 3.5), p.halt_gib);
    try std.testing.expectEqual(@as(f64, 5.0), p.warn_gib); // untouched field keeps the default
}

test "freeGiB reads the real filesystem and roughly matches df" {
    const gib = try freeGiB(".");
    try std.testing.expect(gib > 0.0);
    try std.testing.expect(gib < 250.0); // sanity bound for this environment's disk size
}

test "evaluateTripwires combines all three readings independently" {
    const t = DiskThresholds{};
    const none = evaluateTripwires(evalDiskTier(9.8, t), "checked, consistent", .some_gated);
    try std.testing.expect(!none.any());

    const disk_only = evaluateTripwires(evalDiskTier(1.0, t), "checked, consistent", .some_gated);
    try std.testing.expect(disk_only.disk and !disk_only.drift and !disk_only.decision);

    const drift_only = evaluateTripwires(evalDiskTier(9.8, t), "DRIFT backlog open: dashboard claims 8, live STATE.json says 6\n", .clear);
    try std.testing.expect(drift_only.drift and !drift_only.disk and !drift_only.decision);

    const decision_only = evaluateTripwires(evalDiskTier(9.8, t), "checked, consistent", .all_gated);
    try std.testing.expect(decision_only.decision and !decision_only.disk and !decision_only.drift);
}

test "renderHaltBanner is empty when nothing is halted, non-empty and named otherwise" {
    const clear = try renderHaltBanner(std.testing.allocator, .{}, "");
    defer std.testing.allocator.free(clear);
    try std.testing.expectEqualStrings("", clear);

    const halted = try renderHaltBanner(std.testing.allocator, .{ .disk = true, .decision = true }, "disk 1.2 GiB free; decision B18, B19");
    defer std.testing.allocator.free(halted);
    try std.testing.expect(std.mem.indexOf(u8, halted, "disk") != null);
    try std.testing.expect(std.mem.indexOf(u8, halted, "decision") != null);
    try std.testing.expect(std.mem.indexOf(u8, halted, "B18") != null);
}

test "injectHaltBanner replaces content between markers idempotently" {
    const page = "<div class=\"wrap\">\n" ++ halt_banner_start ++ halt_banner_end ++ "\n<p>rest</p></div>";

    const with_banner = try injectHaltBanner(std.testing.allocator, page, "<div class=\"halt-banner\">HALTED: disk</div>");
    defer std.testing.allocator.free(with_banner);
    try std.testing.expect(std.mem.indexOf(u8, with_banner, "HALTED: disk") != null);
    try std.testing.expect(std.mem.indexOf(u8, with_banner, "<p>rest</p>") != null);

    // Re-injecting empty content on top of an already-injected banner must
    // clear it, not accumulate -- this is what makes a resumed loop's next
    // write actively erase a stale banner instead of leaving it stuck.
    const cleared = try injectHaltBanner(std.testing.allocator, with_banner, "");
    defer std.testing.allocator.free(cleared);
    try std.testing.expect(std.mem.indexOf(u8, cleared, "HALTED") == null);
    try std.testing.expect(std.mem.indexOf(u8, cleared, "<p>rest</p>") != null);
}

test "injectHaltBanner errors loudly when the markers are missing" {
    try std.testing.expectError(Error.MalformedState, injectHaltBanner(std.testing.allocator, "<div>no markers here</div>", "x"));
}
