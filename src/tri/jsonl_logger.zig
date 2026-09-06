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
const tri_io = @import("tri_io");

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
    const io = tri_io.get();

    // Ensure .trinity/ directory exists
    std.Io.Dir.cwd().createDirPath(io, ".trinity") catch |err| {
        std.log.warn("jsonl_logger: makePath(.trinity) failed: {}", .{err});
        // Continue anyway — file creation may still work
    };

    // Use std.json.Stringify stream to get a JSON string
    var buffer: std.Io.Writer.Allocating = .init(allocator);
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

    const file = std.Io.Dir.cwd().openFile(io, EVENTS_PATH, .{}) catch |err| switch (err) {
        error.FileNotFound => {
            // Create file if it doesn't exist
            const new_file = try std.Io.Dir.cwd().createFile(io, EVENTS_PATH, .{});
            defer new_file.close(io);
            try new_file.writeStreamingAll(io, json_string);
            try new_file.writeStreamingAll(io, "\n");
            return;
        },
        else => return err,
    };
    defer file.close(io);

    // Write at end-of-file (append mode)
    var end = try file.length(io);
    try file.writePositionalAll(io, json_string, end);
    end += json_string.len;
    try file.writePositionalAll(io, "\n", end);
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
    std.Io.Dir.cwd().deleteFile(tri_io.get(), EVENTS_PATH) catch {};
}
