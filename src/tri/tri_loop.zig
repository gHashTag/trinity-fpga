//! `tri journal` — read the autonomous cycle's own journal.
//!
//! research/loop-state.md is the memory of the improvement loop: what each
//! iteration did, what it deliberately left alone, and the invariants a later
//! iteration must not violate. Every iteration begins by reading it, and that
//! currently means opening the file and scrolling to the end.
//!
//! This does exactly that and nothing more. It parses no state, tracks no
//! progress and computes no score -- it prints a section of a markdown file.
//! The journal is authoritative; a command that summarised it would introduce
//! a second version of the truth, which is the failure this whole session has
//! been repairing.
//!
//!   tri journal              the most recent iteration entry
//!   tri journal invariants   the rules a new iteration must not break
//!   tri journal all          the whole journal
//!
//! Not `tri loop`: that name already belongs to pipeline step ten,
//! `tri loop decide`, routed to dev_workflow.
//!
//! phi^2 + 1/phi^2 = 3 = TRINITY

const std = @import("std");

const JOURNAL = "research/loop-state.md";
const GOLD = "\x1b[38;2;255;215;0m";
const DIM = "\x1b[38;2;156;156;160m";
const RESET = "\x1b[0m";

pub fn runLoopCommand(allocator: std.mem.Allocator, args: []const []const u8) !void {
    const content = std.fs.cwd().readFileAlloc(allocator, JOURNAL, 4 * 1024 * 1024) catch |err| {
        std.debug.print("{s}no journal at {s}{s} ({s})\n", .{ DIM, JOURNAL, RESET, @errorName(err) });
        std.debug.print("Run this from the repository root.\n", .{});
        return err;
    };
    defer allocator.free(content);

    const mode = if (args.len > 0) args[0] else "latest";

    if (std.mem.eql(u8, mode, "all")) {
        std.debug.print("{s}\n", .{content});
        return;
    }

    if (std.mem.eql(u8, mode, "invariants")) {
        try printSection(content, "## Invariants", "## ");
        return;
    }

    if (!std.mem.eql(u8, mode, "latest")) {
        std.debug.print("Usage: tri journal [latest|invariants|all]\n", .{});
        return error.InvalidArgument;
    }

    // The last "### " heading and everything after it.
    const idx = std.mem.lastIndexOf(u8, content, "\n### ") orelse {
        std.debug.print("{s}journal has no iteration entries yet{s}\n", .{ DIM, RESET });
        return;
    };
    std.debug.print("{s}latest iteration{s}\n", .{ GOLD, RESET });
    std.debug.print("{s}\n", .{content[idx + 1 ..]});
}

/// Print from `heading` up to the next line beginning with `stop`.
fn printSection(content: []const u8, heading: []const u8, stop: []const u8) !void {
    const start = std.mem.indexOf(u8, content, heading) orelse {
        std.debug.print("{s}no '{s}' section in the journal{s}\n", .{ DIM, heading, RESET });
        return;
    };
    const rest = content[start + heading.len ..];
    const end = std.mem.indexOf(u8, rest, stop);
    const body = if (end) |e| rest[0..e] else rest;
    std.debug.print("{s}{s}{s}{s}\n", .{ GOLD, heading, RESET, body });
}

test "latest picks the final iteration heading" {
    const doc =
        \\# Journal
        \\
        \\### 001 — first
        \\did a thing
        \\
        \\### 002 — second
        \\did another
    ;
    const idx = std.mem.lastIndexOf(u8, doc, "\n### ").?;
    try std.testing.expect(std.mem.startsWith(u8, doc[idx + 1 ..], "### 002"));
}

test "a journal with no entries does not crash the search" {
    const doc = "# Journal\n\nnothing yet\n";
    try std.testing.expect(std.mem.lastIndexOf(u8, doc, "\n### ") == null);
}
