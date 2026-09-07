// @origin(manual) @regen(pending)
// ═══════════════════════════════════════════════════════════════════════════════
// QUEEN BRIDGE — Bridge from agent steps to Queen episodes
// ═══════════════════════════════════════════════════════════════════════════════
//
// Each agent step → episode in .trinity/logs/agent-{name}.jsonl
//
// φ² + 1/φ² = 3 = TRINITY
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");
const tri_io = @import("tri_io");
const tri_time = @import("tri_time");
const Allocator = std.mem.Allocator;

pub const StepType = enum {
    start,
    think,
    act,
    observe,
    @"error",
    success,
};

pub const AgentStep = struct {
    agent: []const u8,
    issue_number: u32,
    step_name: []const u8,
    step_type: StepType,
    action: ?[]const u8 = null,
    labels: ?[]const []const u8 = null,
    files: ?[]const []const u8 = null,
    metrics: ?Metrics = null,
    thought: ?[]const u8 = null,
    result: ?[]const u8 = null,
    error_message: ?[]const u8 = null,
    timestamp: i64 = 0,

    pub const Metrics = struct {
        status: ?[]const u8 = null,
        files_changed: ?u32 = null,
        lines_added: ?u32 = null,
        files_touched: ?u32 = null,
    };
};

/// Log an agent step to Queen JSONL format (proper JSON with escaping)
pub fn logStep(allocator: Allocator, step: AgentStep) !void {
    const logs_dir = ".trinity/logs";
    const io = tri_io.get();
    std.Io.Dir.cwd().createDirPath(io, logs_dir) catch {};

    // Build path: .trinity/logs/agent-{name}.jsonl
    var path_buf: [256]u8 = undefined;
    const path = try std.fmt.bufPrint(&path_buf, "{s}/agent-{s}.jsonl", .{
        logs_dir,
        step.agent,
    });

    // Build episode_id: issue-{N}-{step}-{timestamp}
    const ts = if (step.timestamp == 0) tri_time.timestamp() else step.timestamp;
    var id_buf: [128]u8 = undefined;
    const episode_id = try std.fmt.bufPrint(&id_buf, "issue-{d}-{s}-{d}", .{
        step.issue_number,
        step.step_name,
        ts,
    });

    // Map StepType to EpisodeType
    const episode_type: []const u8 = switch (step.step_type) {
        .start => "task",
        .think => "observation",
        .act => "action",
        .observe => "observation",
        .@"error" => "error",
        .success => "task",
    };

    // Build title
    var title_buf: [256]u8 = undefined;
    const title = try std.fmt.bufPrint(&title_buf, "#{d}: {s}", .{
        step.issue_number,
        step.step_name,
    });

    // Build JSON with proper escaping
    var buf: std.ArrayList(u8) = .empty;
    defer buf.deinit(allocator);

    try buf.appendSlice(allocator, "{");
    try buf.appendSlice(allocator, "\"episode_id\":\"");
    try buf.appendSlice(allocator, escapeString(allocator, episode_id));
    try buf.appendSlice(allocator, "\",");
    try buf.appendSlice(allocator, "\"agent\":\"");
    try buf.appendSlice(allocator, escapeString(allocator, step.agent));
    try buf.appendSlice(allocator, "\",");
    try buf.print(allocator, "\"episode_type\":\"{s}\",", .{episode_type});
    try buf.print(allocator, "\"timestamp\":{d},", .{ts});
    try buf.appendSlice(allocator, "\"title\":\"");
    try buf.appendSlice(allocator, escapeString(allocator, title));
    try buf.appendSlice(allocator, "\",");
    try buf.print(allocator, "\"correlation_id\":{d},", .{step.issue_number});
    try buf.appendSlice(allocator, "\"data\":");

    // Build data object
    try buf.appendSlice(allocator, "{");
    try buf.print(allocator, "\"domain\":\"github_issue\"", .{});

    if (step.action) |a| {
        try buf.appendSlice(allocator, ",\"action\":\"");
        try buf.appendSlice(allocator, escapeString(allocator, a));
        try buf.appendSlice(allocator, "\"");
    }
    if (step.labels) |labels| {
        try buf.appendSlice(allocator, ",\"labels\":[");
        for (labels, 0..) |label, i| {
            if (i > 0) try buf.appendSlice(allocator, ",");
            const escaped = escapeString(allocator, label);
            try buf.appendSlice(allocator, "\"");
            try buf.appendSlice(allocator, escaped);
            try buf.appendSlice(allocator, "\"");
        }
        try buf.appendSlice(allocator, "]");
    }
    if (step.files) |files| {
        try buf.appendSlice(allocator, ",\"files\":[");
        for (files, 0..) |file, i| {
            if (i > 0) try buf.appendSlice(allocator, ",");
            const escaped = escapeString(allocator, file);
            try buf.appendSlice(allocator, "\"");
            try buf.appendSlice(allocator, escaped);
            try buf.appendSlice(allocator, "\"");
        }
        try buf.appendSlice(allocator, "]");
    }
    if (step.metrics) |m| {
        try buf.appendSlice(allocator, ",\"metrics\":{");
        var need_comma = false;
        if (m.status) |s| {
            try buf.appendSlice(allocator, "\"status\":\"");
            try buf.appendSlice(allocator, escapeString(allocator, s));
            try buf.appendSlice(allocator, "\"");
            need_comma = true;
        }
        if (m.files_changed) |fc| {
            if (need_comma) try buf.appendSlice(allocator, ",");
            try buf.print(allocator, "\"files_changed\":{d}", .{fc});
            need_comma = true;
        }
        if (m.lines_added) |la| {
            if (need_comma) try buf.appendSlice(allocator, ",");
            try buf.print(allocator, "\"lines_added\":{d}", .{la});
            need_comma = true;
        }
        if (m.files_touched) |ft| {
            if (need_comma) try buf.appendSlice(allocator, ",");
            try buf.print(allocator, "\"files_touched\":{d}", .{ft});
        }
        try buf.appendSlice(allocator, "}");
    }
    if (step.thought) |t| {
        try buf.appendSlice(allocator, ",\"thought\":\"");
        try buf.appendSlice(allocator, escapeString(allocator, t));
        try buf.appendSlice(allocator, "\"");
    }
    if (step.result) |r| {
        try buf.appendSlice(allocator, ",\"next_step\":\"");
        try buf.appendSlice(allocator, escapeString(allocator, r));
        try buf.appendSlice(allocator, "\"");
    }
    if (step.error_message) |e| {
        try buf.appendSlice(allocator, ",\"error\":\"");
        try buf.appendSlice(allocator, escapeString(allocator, e));
        try buf.appendSlice(allocator, "\"");
    }

    try buf.appendSlice(allocator, "}"); // Close data object
    try buf.appendSlice(allocator, "}"); // Close episode object

    // Open file for append
    const file = try std.Io.Dir.cwd().createFile(io, path, .{ .truncate = false });
    defer file.close(io);
    // 0.16 has no seekFromEnd; appending is an explicit positional write at the
    // current length. The newline joins the payload so one jsonl record is a
    // single write rather than two.
    try buf.append(allocator, '\n');
    const end = try file.length(io);
    try file.writePositionalAll(io, buf.items, end);
}

/// Escape JSON string (minimal: quotes, backslashes, newlines)
/// Returns escaped string (caller owns memory)
fn escapeString(allocator: Allocator, s: []const u8) []const u8 {
    var escaped: std.ArrayList(u8) = .empty;
    defer escaped.deinit(allocator);

    for (s) |c| {
        switch (c) {
            '\\' => escaped.appendSlice(allocator, "\\\\") catch {},
            '"' => escaped.appendSlice(allocator, "\\\"") catch {},
            '\n' => escaped.appendSlice(allocator, "\\n") catch {},
            '\r' => escaped.appendSlice(allocator, "\\r") catch {},
            '\t' => escaped.appendSlice(allocator, "\\t") catch {},
            else => escaped.append(allocator, c) catch {},
        }
    }

    return escaped.toOwnedSlice(allocator) catch s;
}

/// Convenience: log step start
pub fn logStepStart(allocator: Allocator, agent: []const u8, issue: u32, step_name: []const u8, thought: ?[]const u8) !void {
    try logStep(allocator, .{
        .agent = agent,
        .issue_number = issue,
        .step_name = step_name,
        .step_type = .start,
        .thought = thought,
    });
}

/// Convenience: log step success
pub fn logStepSuccess(allocator: Allocator, agent: []const u8, issue: u32, step_name: []const u8, result: ?[]const u8) !void {
    try logStep(allocator, .{
        .agent = agent,
        .issue_number = issue,
        .step_name = step_name,
        .step_type = .success,
        .result = result,
    });
}

/// Convenience: log step error
pub fn logStepError(allocator: Allocator, agent: []const u8, issue: u32, step_name: []const u8, error_msg: []const u8) !void {
    try logStep(allocator, .{
        .agent = agent,
        .issue_number = issue,
        .step_name = step_name,
        .step_type = .@"error",
        .error_message = error_msg,
    });
}

// ═════════════════════════════════════════════════════════════════════════════
// GitHub Episode API — for γ agent to log issue work
// ═════════════════════════════════════════════════════════════════════════════

/// Start working on a GitHub issue
pub fn logGitHubIssueStart(allocator: Allocator, agent: []const u8, issue_number: u32, title: []const u8, labels: []const []const u8) !void {
    try logStep(allocator, .{
        .agent = agent,
        .issue_number = issue_number,
        .step_name = title,
        .step_type = .start,
        .action = "issue.start",
        .labels = labels,
    });
}

/// Record a step within an issue
pub fn logGitHubIssueStep(allocator: Allocator, agent: []const u8, issue_number: u32, description: []const u8, files: []const []const u8) !void {
    try logStep(allocator, .{
        .agent = agent,
        .issue_number = issue_number,
        .step_name = description,
        .step_type = .act,
        .action = "issue.step",
        .files = files,
    });
}

/// Complete an issue successfully
pub fn logGitHubIssueComplete(allocator: Allocator, agent: []const u8, issue_number: u32, status: []const u8, files_changed: u32, lines_added: u32) !void {
    try logStep(allocator, .{
        .agent = agent,
        .issue_number = issue_number,
        .step_name = "Issue complete",
        .step_type = .success,
        .action = "issue.complete",
        .metrics = .{
            .status = status,
            .files_changed = files_changed,
            .lines_added = lines_added,
        },
    });
}

/// Log issue failure
pub fn logGitHubIssueFail(allocator: Allocator, agent: []const u8, issue_number: u32, error_message: []const u8, files_touched: u32) !void {
    try logStep(allocator, .{
        .agent = agent,
        .issue_number = issue_number,
        .step_name = "Issue failed",
        .step_type = .@"error",
        .action = "issue.fail",
        .error_message = error_message,
        .metrics = .{
            .files_touched = files_touched,
        },
    });
}
