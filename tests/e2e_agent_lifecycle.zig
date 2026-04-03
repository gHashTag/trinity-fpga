//! E2E Test: Agent Lifecycle (Issue E)
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const Allocator = std.mem.Allocator;

test "e2e: SOUL.md template exists" {
    // Verify template file exists and has required sections
    const content = try std.fs.cwd().readFileAlloc(std.testing.allocator, "templates/SOUL.md", .{});
    defer std.testing.allocator.free(content);

    // Check for required sections
    try std.testing.expect(std.mem.indexOf(u8, content, "Agent Identity") != null);
    try std.testing.expect(std.mem.indexOf(u8, content, "Mission") != null);
    try std.testing.expect(std.mem.indexOf(u8, content, "Allowed Commands") != null);
    try std.testing.expect(std.mem.indexOf(u8, content, "Stop Conditions") != null);
    try std.testing.expect(std.mem.indexOf(u8, content, "Reporting Format") != null);
    try std.testing.expect(std.mem.indexOf(u8, content, "References") != null);
}

test "e2e: issue_bindings.json exists" {
    // Verify bindings file exists with correct structure
    const content = try std.fs.cwd().readFileAlloc(std.testing.allocator, ".trinity/issue_bindings.json", .{});
    defer std.testing.allocator.free(content);

    // Check for required fields
    try std.testing.expect(std.mem.indexOf(u8, content, "bindings") != null);
    try std.testing.expect(std.mem.indexOf(u8, content, "version") != null);
    try std.testing.expect(std.mem.indexOf(u8, content, "last_updated") != null);
}
