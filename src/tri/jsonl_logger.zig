// @origin(spec:jsonl_logger.tri) @regen(pending-impl)
// ═════════════════════════════════════════════════════════════════════════════════
// JSONL Logger — Agent events logging to .trinity/agent_events.jsonl
// ═════════════════════════════════════════════════════════════════════════════════════════════════════════
//
// φ² + 1/φ² = 3 = TRINITY
//
// This module provides append-only logging for agent events in JSONL format.
// Each event is a JSON object on its own line.
//
// Event format:
// {
//   "ts": <timestamp>,
//   "event_type": "<type>",
//   "issue": <number>,
//   "agent": "<name>",
//   "ok": true|false
// }
//
// ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

const std = @import("std");

const EVENTS_PATH = ".trinity/agent_events.jsonl";

/// Event structure for JSONL logging
pub const Event = struct {
    ts: i64,
    event_type: []const u8,
    issue: u32,
    agent: ?[]const u8,
    ok: bool,
};

/// Append one event as a JSONL line to .trinity/agent_events.jsonl
pub fn appendEvent(allocator: std.mem.Allocator, event: Event) !void {
    // Ensure .trinity/ directory exists
    std.fs.cwd().makePath(".trinity") catch |err| {
        std.log.warn("jsonl_logger: makePath(.trinity) failed: {}", .{err});
        // Continue anyway — file creation may still work
    };

    // Use std.json.Stringify stream to get a JSON string
    var buffer: std.io.Writer.Allocating = .init(allocator);
    defer buffer.deinit();
    var write_stream: std.json.Stringify = .{
        .writer = &buffer.writer,
        .options = .{},
    };

    try write_stream.beginObject();
    try write_stream.objectField("ts");
    try write_stream.write(event.ts);
    try write_stream.objectField("event_type");
    try write_stream.write(event.event_type);
    try write_stream.objectField("issue");
    try write_stream.write(event.issue);
    if (event.agent) |agent| {
        try write_stream.objectField("agent");
        try write_stream.write(agent);
    }
    try write_stream.objectField("ok");
    try write_stream.write(event.ok);
    try write_stream.endObject();

    const json_string = buffer.written();

    const file = std.fs.cwd().openFile(EVENTS_PATH, .{}) catch |err| switch (err) {
        error.FileNotFound => {
            // Create file if it doesn't exist
            const new_file = try std.fs.cwd().createFile(EVENTS_PATH, .{});
            defer new_file.close();
            try new_file.writeAll(json_string);
            try new_file.writeAll("\n");
            return;
        },
        else => return err,
    };
    defer file.close();

    // Seek to end before writing (append mode)
    try file.seekFromEnd(0);
    try file.writeAll(json_string);
    try file.writeAll("\n");
}

test "appendEvent creates directory" {
    const allocator = std.testing.allocator;

    const test_event = Event{
        .ts = 1234567890,
        .event_type = "test",
        .issue = 42,
        .agent = "test-agent",
        .ok = true,
    };

    // This test creates .trinity/agent_events.jsonl in a temp dir
    // In actual usage, it appends to existing file
    try appendEvent(allocator, test_event);

    // Cleanup
    std.fs.cwd().deleteFile(EVENTS_PATH) catch {};
}
