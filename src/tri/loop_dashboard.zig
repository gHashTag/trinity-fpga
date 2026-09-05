//! Generates the loop's status dashboard from STATE.json.
//!
//! Why a generator instead of editing the page: `.trinity/loop/dashboard.html`
//! is 164 KB of hand-written narrative that accreted over a hundred iterations,
//! and its numbers drift from STATE.json whenever someone updates one and not
//! the other. That drift is real -- `tri-loopstate check` exists solely to catch
//! it, and has. A page derived from the state file cannot drift from it.
//!
//! The old page is NOT replaced. It is the loop's historical record and stays
//! exactly as it is; this writes a separate file. Nothing that reads the old one
//! changes behaviour.
//!
//! ## The contract this output must satisfy
//!
//! `tri_loopstate.zig` both reads and rewrites dashboard HTML, so this is not
//! free-form markup. Three things are load-bearing:
//!
//!   1. `<div class="readout">` -- the anchor that scopes number extraction.
//!      Everything before it is deliberately out of scope, because the halt
//!      banner sits above it and can echo a label's own words.
//!   2. Inside it, `<div class="n">N</div><div class="l">label</div>` cells for
//!      at least "backlog open" and "anomalies open", n before l.
//!   3. `<!-- LOOP_HALT_BANNER_START -->` / `<!-- LOOP_HALT_BANNER_END -->`,
//!      and CSS variables `--bad` and `--paper`, which the injected banner
//!      markup references.
//!
//! These are asserted by running the real reader against real generated output
//! -- `checkDrift` must return "checked, consistent" for a freshly rendered
//! page -- rather than by eyeballing the HTML. A comment saying "keep the
//! readout div" is what the old page had.
//!
//! phi^2 + 1/phi^2 = 3 = TRINITY

const std = @import("std");
const loopstate = @import("tri_loopstate.zig");

pub const default_output_path = ".trinity/loop/status.html";

/// Escape text taken from STATE.json before it lands in HTML.
///
/// Not optional: the state file's prose is full of `<`, `>` and `&` -- backlog
/// rows quote Zig generics and shell redirections, anomaly text quotes error
/// messages. Interpolating it raw produces a page that renders wrong in ways
/// that look like missing data rather than broken markup.
fn escape(allocator: std.mem.Allocator, out: *std.ArrayList(u8), s: []const u8) !void {
    for (s) |c| switch (c) {
        '&' => try out.appendSlice(allocator, "&amp;"),
        '<' => try out.appendSlice(allocator, "&lt;"),
        '>' => try out.appendSlice(allocator, "&gt;"),
        '"' => try out.appendSlice(allocator, "&quot;"),
        '\'' => try out.appendSlice(allocator, "&#39;"),
        else => try out.append(allocator, c),
    };
}

/// Read a string field, falling back rather than erroring: a dashboard that
/// renders with one field missing is more useful than one that refuses to
/// render at all.
fn strField(v: std.json.Value, key: []const u8, fallback: []const u8) []const u8 {
    const o = switch (v) {
        .object => |obj| obj,
        else => return fallback,
    };
    const f = o.get(key) orelse return fallback;
    return switch (f) {
        .string => |s| if (s.len == 0) fallback else s,
        else => fallback,
    };
}

fn arrayField(root: std.json.Value, key: []const u8) []const std.json.Value {
    const o = switch (root) {
        .object => |obj| obj,
        else => return &.{},
    };
    const f = o.get(key) orelse return &.{};
    return switch (f) {
        .array => |a| a.items,
        else => &.{},
    };
}

/// True when a backlog row is not finished. Mirrors `liveCounts`' rule exactly
/// -- "open unless status is exactly completed" -- because if this drifted from
/// that, the table and the number above it would disagree on the same page.
fn backlogRowOpen(row: std.json.Value) bool {
    return !std.mem.eql(u8, strField(row, "status", "pending"), "completed");
}

fn truncated(s: []const u8, limit: usize) []const u8 {
    if (s.len <= limit) return s;
    // Cut on a space when there is one nearby, so the break lands between words
    // instead of mid-token.
    var cut = limit;
    while (cut > limit -| 24) : (cut -= 1) {
        if (s[cut] == ' ') return s[0..cut];
    }
    return s[0..limit];
}

/// Escape `s`, appending an ellipsis when it was actually cut short.
///
/// The marker is not decoration. Rendered without it, a truncated backlog note
/// ends mid-sentence and reads as corrupted state rather than as elision -- seen
/// on the first generated page, where "found stale by the periodic" looked like
/// data loss.
fn escapeTruncated(allocator: std.mem.Allocator, out: *std.ArrayList(u8), s: []const u8, limit: usize) !void {
    const cut = truncated(s, limit);
    try escape(allocator, out, cut);
    if (cut.len < s.len) try out.appendSlice(allocator, "&hellip;");
}

const style =
    \\<style>
    \\  :root {
    \\    --paper: #FAF9F5; --panel: #FFFFFF; --ink: #141413; --dim: #73716C;
    \\    --rule: #E8E5DC; --accent: #D97757; --ok: #5F8A6B; --warn: #C08A2E;
    \\    --bad: #BF4722; --mono: ui-monospace, "SF Mono", Menlo, "JetBrains Mono", monospace;
    \\  }
    \\  @media (prefers-color-scheme: dark) {
    \\    :root {
    \\      --paper: #1F1E1D; --panel: #262624; --ink: #F0EEE6; --dim: #9A968D;
    \\      --rule: #35332F; --accent: #E08A6B; --ok: #7FA98A; --warn: #D6A445;
    \\      --bad: #E0674080;
    \\    }
    \\  }
    \\  :root[data-theme="dark"] {
    \\    --paper: #1F1E1D; --panel: #262624; --ink: #F0EEE6; --dim: #9A968D;
    \\    --rule: #35332F; --accent: #E08A6B; --ok: #7FA98A; --warn: #D6A445;
    \\    --bad: #E06740;
    \\  }
    \\  :root[data-theme="light"] {
    \\    --paper: #FAF9F5; --panel: #FFFFFF; --ink: #141413; --dim: #73716C;
    \\    --rule: #E8E5DC; --accent: #D97757; --ok: #5F8A6B; --warn: #C08A2E;
    \\    --bad: #BF4722;
    \\  }
    \\  body {
    \\    margin: 0; padding: 2.2rem 1.4rem 4rem; background: var(--paper); color: var(--ink);
    \\    font: 15px/1.6 ui-sans-serif, -apple-system, "Segoe UI", system-ui, sans-serif;
    \\    -webkit-font-smoothing: antialiased;
    \\  }
    \\  .wrap { max-width: 62rem; margin: 0 auto; }
    \\  .masthead { display: flex; flex-wrap: wrap; align-items: baseline; gap: .6rem 1rem;
    \\    padding-bottom: 1rem; border-bottom: 1px solid var(--rule); }
    \\  .masthead h1 { font: 600 1.05rem/1.2 var(--mono); margin: 0; letter-spacing: -.01em; }
    \\  .masthead .it { font: 600 1.05rem/1.2 var(--mono); color: var(--accent); }
    \\  .pill { font: 500 11px/1 var(--mono); text-transform: uppercase; letter-spacing: .08em;
    \\    padding: .32rem .55rem; border-radius: 3px; border: 1px solid var(--rule); color: var(--dim); }
    \\  .pill.run { color: var(--ok); border-color: color-mix(in srgb, var(--ok) 42%, transparent); }
    \\  .pill.halt { color: var(--bad); border-color: color-mix(in srgb, var(--bad) 50%, transparent); }
    \\  .stamp { margin-left: auto; font: 11px/1 var(--mono); color: var(--dim); }
    \\  .readout { display: grid; grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
    \\    gap: 1px; background: var(--rule); border: 1px solid var(--rule);
    \\    border-radius: 4px; overflow: hidden; margin: 1.6rem 0 2.2rem; }
    \\  .cellstat { background: var(--panel); padding: .95rem 1rem; }
    \\  .cellstat .n { font: 600 1.55rem/1.05 var(--mono); letter-spacing: -.02em; }
    \\  .cellstat .l { font: 11px/1.35 var(--mono); color: var(--dim); text-transform: uppercase;
    \\    letter-spacing: .07em; margin-top: .3rem; }
    \\  h2 { font: 600 12px/1 var(--mono); text-transform: uppercase; letter-spacing: .1em;
    \\    color: var(--dim); margin: 2.2rem 0 .85rem; }
    \\  .rows { border: 1px solid var(--rule); border-radius: 4px; overflow: hidden; }
    \\  .row { display: grid; grid-template-columns: 4.2rem 6.5rem 1fr; gap: .85rem;
    \\    padding: .7rem .9rem; background: var(--panel); border-top: 1px solid var(--rule); }
    \\  .row:first-child { border-top: 0; }
    \\  .row .id { font: 600 12px/1.5 var(--mono); color: var(--accent); }
    \\  .row .st { font: 11px/1.5 var(--mono); color: var(--dim); text-transform: uppercase;
    \\    letter-spacing: .05em; }
    \\  .row .st.blocked { color: var(--warn); }
    \\  .row .wt { font-size: 13.5px; min-width: 0; overflow-wrap: anywhere; }
    \\  .row .wt .by { display: block; margin-top: .3rem; font: 11.5px/1.5 var(--mono); color: var(--dim); }
    \\  .empty { padding: .9rem; border: 1px dashed var(--rule); border-radius: 4px;
    \\    color: var(--dim); font: 12px/1.5 var(--mono); }
    \\  ol.coop { counter-reset: c; list-style: none; padding: 0; margin: 0; display: grid; gap: .6rem; }
    \\  ol.coop li { counter-increment: c; background: var(--panel); border: 1px solid var(--rule);
    \\    border-radius: 4px; padding: .8rem .95rem .8rem 2.6rem; position: relative; font-size: 13.5px; }
    \\  ol.coop li::before { content: counter(c); position: absolute; left: .95rem; top: .8rem;
    \\    font: 600 12px/1.5 var(--mono); color: var(--accent); }
    \\  footer { margin-top: 2.6rem; padding-top: 1rem; border-top: 1px solid var(--rule);
    \\    font: 11px/1.7 var(--mono); color: var(--dim); }
    \\  @media (max-width: 34rem) { .row { grid-template-columns: 3.6rem 1fr; }
    \\    .row .st { grid-column: 2; margin-top: -.4rem; } }
    \\</style>
;

/// Render the whole page. `generated_note` is free text for the footer (the
/// caller supplies it because this module cannot read a clock).
pub fn render(
    allocator: std.mem.Allocator,
    st: *const loopstate.State,
    generated_note: []const u8,
) ![]u8 {
    const live = loopstate.liveCounts(st);
    const root = st.root();
    const loop = switch (root) {
        .object => |o| o.get("loop") orelse std.json.Value{ .null = {} },
        else => std.json.Value{ .null = {} },
    };

    var gate = try loopstate.decisionGateStatus(allocator, st);
    defer gate.deinit(allocator);

    var out: std.ArrayList(u8) = .empty;
    errdefer out.deinit(allocator);
    const a = allocator;

    try out.appendSlice(a, "<title>Trinity Loop — status</title>\n");
    try out.appendSlice(a, style);
    try out.appendSlice(a, "\n<div class=\"wrap\">\n");

    // The halt banner goes ABOVE everything, and its markers must exist even
    // when nothing is halted -- injectHaltBanner errors loudly on a page that
    // lacks them, which is the correct behaviour and would make every tripwire
    // run fail against a page rendered without them.
    try out.appendSlice(a, "<!-- LOOP_HALT_BANNER_START --><!-- LOOP_HALT_BANNER_END -->\n");

    const status = strField(loop, "status", "UNKNOWN");
    const halted = std.mem.indexOf(u8, status, "HALT") != null;
    try out.appendSlice(a, "  <div class=\"masthead\">\n    <h1>TRINITY LOOP</h1>\n");
    try out.print(a, "    <span class=\"it\">iteration {d}</span>\n", .{st.iteration});
    try out.print(a, "    <span class=\"pill {s}\">", .{if (halted) "halt" else "run"});
    try escape(a, &out, status);
    try out.appendSlice(a, "</span>\n");
    try out.appendSlice(a, "    <span class=\"pill\">");
    try escape(a, &out, strField(loop, "cooperation_mode", "unspecified"));
    try out.appendSlice(a, "</span>\n    <span class=\"stamp\">");
    try escape(a, &out, generated_note);
    try out.appendSlice(a, "</span>\n  </div>\n\n");

    // ---- readout block: the machine-read part. Nothing but cells in here. ----
    try out.appendSlice(a, "  <div class=\"readout\">\n");
    const cells = [_]struct { n: usize, l: []const u8 }{
        .{ .n = live.done_count, .l = "done" },
        .{ .n = live.backlog_open, .l = "backlog open" },
        .{ .n = live.backlog_total, .l = "backlog total" },
        .{ .n = live.anomalies_open, .l = "anomalies open" },
        .{ .n = live.anomalies_total, .l = "anomalies total" },
    };
    for (cells) |c| {
        try out.print(
            a,
            "    <div class=\"cellstat\"><div class=\"n\">{d}</div><div class=\"l\">{s}</div></div>\n",
            .{ c.n, c.l },
        );
    }
    try out.appendSlice(a, "  </div>\n\n");

    // ---- decision gate ----
    try out.appendSlice(a, "  <h2>Decision gate</h2>\n  <div class=\"empty\">gate: ");
    try escape(a, &out, @tagName(gate.status));
    if (gate.gated_ids.items.len > 0) {
        // Listed whatever the status, per DecisionGate's own contract: rows can
        // be gated without being what blocks the loop, and collapsing those two
        // into one line is how "clear" gets misread as "nothing is waiting".
        try out.appendSlice(a, " &mdash; awaiting a decision: ");
        for (gate.gated_ids.items, 0..) |id, i| {
            if (i > 0) try out.appendSlice(a, ", ");
            try escape(a, &out, id);
        }
    }
    try out.appendSlice(a, "</div>\n");

    // ---- open backlog ----
    try out.appendSlice(a, "\n  <h2>Backlog &mdash; open</h2>\n");
    const backlog = arrayField(root, "backlog");
    var open_rows: usize = 0;
    for (backlog) |row| {
        if (backlogRowOpen(row)) open_rows += 1;
    }
    if (open_rows == 0) {
        try out.appendSlice(a, "  <div class=\"empty\">no open rows</div>\n");
    } else {
        try out.appendSlice(a, "  <div class=\"rows\">\n");
        for (backlog) |row| {
            if (!backlogRowOpen(row)) continue;
            const blocked_by = arrayField(row, "blocked_by");
            try out.appendSlice(a, "    <div class=\"row\"><div class=\"id\">");
            try escape(a, &out, strField(row, "id", "?"));
            try out.print(a, "</div><div class=\"st{s}\">", .{if (blocked_by.len > 0) " blocked" else ""});
            try escape(a, &out, strField(row, "status", "pending"));
            try out.appendSlice(a, "</div><div class=\"wt\">");
            try escapeTruncated(a, &out, strField(row, "title", strField(row, "what", "—")), 240);
            if (blocked_by.len > 0) {
                try out.appendSlice(a, "<span class=\"by\">blocked by: ");
                for (blocked_by, 0..) |b, i| {
                    if (i > 0) try out.appendSlice(a, "; ");
                    try escapeTruncated(a, &out, switch (b) {
                        .string => |s| s,
                        else => "(non-string)",
                    }, 150);
                }
                try out.appendSlice(a, "</span>");
            }
            try out.appendSlice(a, "</div></div>\n");
        }
        try out.appendSlice(a, "  </div>\n");
    }

    // ---- collaboration options ----
    const coop = arrayField(root, "collaboration_options");
    if (coop.len > 0) {
        try out.appendSlice(a, "\n  <h2>Collaboration options for the next loop</h2>\n  <ol class=\"coop\">\n");
        for (coop) |c| {
            try out.appendSlice(a, "    <li>");
            switch (c) {
                .string => |s| try escape(a, &out, s),
                .object => {
                    try escape(a, &out, strField(c, "title", strField(c, "option", "—")));
                    const body = strField(c, "detail", strField(c, "what", ""));
                    if (body.len > 0) {
                        try out.appendSlice(a, "<span class=\"by\">");
                        try escape(a, &out, body);
                        try out.appendSlice(a, "</span>");
                    }
                },
                else => try out.appendSlice(a, "&mdash;"),
            }
            try out.appendSlice(a, "</li>\n");
        }
        try out.appendSlice(a, "  </ol>\n");
    }

    try out.appendSlice(a, "\n  <footer>Generated by <code>tri-loopstate render</code> from ");
    try escape(a, &out, loopstate.default_state_path);
    try out.appendSlice(a,
        \\.<br>Numbers here are read from that file at render time, so they cannot drift from it.
        \\  The narrative record lives in dashboard.html and JOURNAL.md.</footer>
        \\</div>
        \\
    );

    return out.toOwnedSlice(a);
}

// ---------------------------------------------------------------------------

const fixture =
    \\{
    \\  "loop": {"id":"t","iteration":105,"status":"RUNNING","cooperation_mode":"autonomous_with_tripwires"},
    \\  "done": [{"id":"D1","what":"a"},{"id":"D2","what":"b"}],
    \\  "backlog": [
    \\    {"id":"B1","prio":1,"what":"open & <unblocked>","blocked_by":[],"status":"pending"},
    \\    {"id":"B2","prio":2,"what":"waiting","blocked_by":["something else"],"status":"pending"},
    \\    {"id":"B3","prio":3,"what":"finished","blocked_by":[],"status":"completed"}
    \\  ],
    \\  "anomalies": [{"id":"A1","status":""},{"id":"A2","status":"fixed"}],
    \\  "collaboration_options": ["keep going", {"title":"pick one","detail":"and say why"}]
    \\}
;

test "render output satisfies the drift-checker it will be read by" {
    var st = try loopstate.parse(std.testing.allocator, fixture);
    defer st.deinit();

    const html = try render(std.testing.allocator, &st, "test");
    defer std.testing.allocator.free(html);

    // The real reader, against real generated output. This is the assertion
    // that matters: if the readout markup ever stops matching what
    // findReadoutDigits expects, this fails here rather than as a mystery
    // MISSING report during a live tripwire run.
    const live = loopstate.liveCounts(&st);
    const report = try loopstate.checkDrift(std.testing.allocator, live, html);
    defer std.testing.allocator.free(report);

    // checkDrift emits a per-label "ok" line before its summary, so this asserts
    // on the two things that actually carry meaning rather than on the exact
    // string. The first version of this test demanded an exact match and failed
    // against output that was entirely correct.
    try std.testing.expect(std.mem.indexOf(u8, report, "checked, consistent") != null);
    try std.testing.expect(std.mem.indexOf(u8, report, "DRIFT") == null);
    try std.testing.expect(std.mem.indexOf(u8, report, "MISSING") == null);

    // And the same predicate evaluateTripwires uses, so a page rendered by this
    // module can never itself trip the drift tripwire.
    const reasons = loopstate.evaluateTripwires(.full, report, .clear);
    try std.testing.expect(!reasons.any());
}

test "render exposes both machine-read numbers at their real values" {
    var st = try loopstate.parse(std.testing.allocator, fixture);
    defer st.deinit();
    const html = try render(std.testing.allocator, &st, "test");
    defer std.testing.allocator.free(html);

    // 2 of 3 backlog rows open (B3 is completed); 1 of 2 anomalies open.
    try std.testing.expectEqual(@as(?i64, 2), loopstate.extractReadoutNumber(html, "backlog open"));
    try std.testing.expectEqual(@as(?i64, 1), loopstate.extractReadoutNumber(html, "anomalies open"));
}

test "render leaves a halt banner slot the injector can actually write to" {
    var st = try loopstate.parse(std.testing.allocator, fixture);
    defer st.deinit();
    const html = try render(std.testing.allocator, &st, "test");
    defer std.testing.allocator.free(html);

    const banner = try loopstate.renderHaltBanner(
        std.testing.allocator,
        .{ .disk = true, .drift = false, .decision = false },
        "0.4 GiB free",
    );
    defer std.testing.allocator.free(banner);

    const injected = try loopstate.injectHaltBanner(std.testing.allocator, html, banner);
    defer std.testing.allocator.free(injected);
    try std.testing.expect(std.mem.indexOf(u8, injected, "HALTED") != null);

    // And the banner's own prose must not capture the readout labels -- the
    // exact bug findReadoutDigits was written to survive.
    try std.testing.expectEqual(@as(?i64, 2), loopstate.extractReadoutNumber(injected, "backlog open"));
}

test "render escapes state text instead of emitting it as markup" {
    var st = try loopstate.parse(std.testing.allocator, fixture);
    defer st.deinit();
    const html = try render(std.testing.allocator, &st, "test");
    defer std.testing.allocator.free(html);

    try std.testing.expect(std.mem.indexOf(u8, html, "open &amp; &lt;unblocked&gt;") != null);
    try std.testing.expect(std.mem.indexOf(u8, html, "<unblocked>") == null);
}

test "render omits completed rows from the table but still counts them in totals" {
    var st = try loopstate.parse(std.testing.allocator, fixture);
    defer st.deinit();
    const html = try render(std.testing.allocator, &st, "test");
    defer std.testing.allocator.free(html);

    try std.testing.expect(std.mem.indexOf(u8, html, "\"id\">B1<") != null);
    try std.testing.expect(std.mem.indexOf(u8, html, "\"id\">B2<") != null);
    try std.testing.expect(std.mem.indexOf(u8, html, "\"id\">B3<") == null);
    try std.testing.expectEqual(@as(?i64, 3), loopstate.extractReadoutNumber(html, "backlog total"));
}

test "render survives a state file missing every optional section" {
    const minimal =
        \\{"loop":{"iteration":1},"done":[],"backlog":[]}
    ;
    var st = try loopstate.parse(std.testing.allocator, minimal);
    defer st.deinit();
    const html = try render(std.testing.allocator, &st, "");
    defer std.testing.allocator.free(html);

    try std.testing.expect(std.mem.indexOf(u8, html, "no open rows") != null);
    try std.testing.expectEqual(@as(?i64, 0), loopstate.extractReadoutNumber(html, "backlog open"));
}
