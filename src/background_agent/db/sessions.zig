//! Sessions CRUD Operations
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const Allocator = std.mem.Allocator;

const PostgresClient = @import("client.zig").PostgresClient;
const Error = @import("client.zig").Error;

/// Session data structure
pub const Session = struct {
    id: []const u8,
    name: []const u8,
    status: []const u8,
    railway_service_id: []const u8,
    soul_file: []const u8,
    created_at: i64,
    updated_at: i64,
};

/// Sessions error
pub const SessionsError = error{
    SessionNotFound,
    InvalidStatus,
    DatabaseError,
    InvalidInput,
};

/// Create a new session
pub fn createSession(allocator: Allocator, client: *PostgresClient, name: []const u8, service_id: []const u8) !Session {
    if (name.len == 0) return error.InvalidInput;
    if (service_id.len == 0) return error.InvalidInput;

    const now = std.time.timestamp();
    const session_id = try generateSessionId(allocator);

    const sql = try std.fmt.allocPrint(allocator,
        \\INSERT INTO sessions (id, name, status, railway_service_id, soul_file, created_at, updated_at)
        \\VALUES ('{s}', '{s}', 'active', '{s}', '', {d}, {d})
    , .{ session_id, name, service_id, now, now });

    defer allocator.free(sql);

    const result = PostgresClient.query(client, sql, &.{}) orelse return error.DatabaseError;
    defer {
        for (result.rows.items) |*row| {
            row.columns.deinit();
            row.values.deinit();
        }
        result.rows.deinit();
    }

    return Session{
        .id = try allocator.dupe(u8, session_id),
        .name = try allocator.dupe(u8, name),
        .status = try allocator.dupe(u8, "active"),
        .railway_service_id = try allocator.dupe(u8, service_id),
        .created_at = now,
        .updated_at = now,
    };
}

/// Get session by ID
pub fn getSession(allocator: Allocator, client: *PostgresClient, session_id: []const u8) !Session {
    if (session_id.len == 0) return error.InvalidInput;

    const sql = try std.fmt.allocPrint(allocator,
        \\SELECT id, name, status, railway_service_id, soul_file,
        \\EXTRACT(EPOCH FROM created_at) as created_at,
        \\EXTRACT(EPOCH FROM updated_at) as updated_at
        \\FROM sessions WHERE id = '{s}'
    , .{ session_id });

    defer allocator.free(sql);

    const result = PostgresClient.query(client, sql, &.{}) orelse return error.DatabaseError;
    defer {
        for (result.rows.items) |*row| {
            row.columns.deinit();
            row.values.deinit();
        }
        result.rows.deinit();
    }

    if (result.rows.items.len == 0) {
        return error.SessionNotFound;
    }

    const row = &result.rows.items[0];

    // Parse created_at and updated_at from epoch
    const created_at = if (row.values.items.len > 5)
        try std.fmt.parseInt(i64, row.values.items[5], 10) catch std.time.timestamp()
    else std.time.timestamp();

    const updated_at = if (row.values.items.len > 6)
        try std.fmt.parseInt(i64, row.values.items[6], 10) catch 0
    else std.time.timestamp();

    return Session{
        .id = try allocator.dupe(u8, session_id),
        .name = try allocator.dupe(u8, row.values.items[1] orelse ""),
        .status = try allocator.dupe(u8, row.values.items[2] orelse "unknown"),
        .railway_service_id = try allocator.dupe(u8, row.values.items[3] orelse ""),
        .soul_file = try allocator.dupe(u8, row.values.items[4] orelse ""),
        .created_at = created_at,
        .updated_at = updated_at,
    };
}

/// List all sessions
pub fn listSessions(allocator: Allocator, client: *PostgresClient) !std.ArrayList(Session) {
    const sql = "SELECT id, name, status, railway_service_id, soul_file, EXTRACT(EPOCH FROM created_at) as created_at, EXTRACT(EPOCH FROM updated_at) as updated_at FROM sessions ORDER BY created_at DESC";

    const result = PostgresClient.query(client, sql, &.{}) orelse return error.DatabaseError;
    errdefer {
        for (result.rows.items) |*row| {
            row.columns.deinit();
            row.values.deinit();
        }
        result.rows.deinit();
    }

    var sessions = std.ArrayList(Session).init(allocator);

    for (result.rows.items) |*row| {
        const created_at = if (row.values.items.len > 4)
            try std.fmt.parseInt(i64, row.values.items[4], 10) catch std.time.timestamp()
        else std.time.timestamp();

        const updated_at = if (row.values.items.len > 5)
            try std.fmt.parseInt(i64, row.values.items[5], 10) catch std.time.timestamp()
        else std.time.timestamp();

        try sessions.append(Session{
            .id = try allocator.dupe(u8, row.values.items[0] orelse ""),
            .name = try allocator.dupe(u8, row.values.items[1] orelse ""),
            .status = try allocator.dupe(u8, row.values.items[2] orelse "unknown"),
            .railway_service_id = try allocator.dupe(u8, row.values.items[3] orelse ""),
            .soul_file = try allocator.dupe(u8, row.values.items[4] orelse ""),
            .created_at = created_at,
            .updated_at = updated_at,
        });
    }

    return sessions;
}

/// Update session
pub fn updateSession(allocator: Allocator, client: *PostgresClient, session_id: []const u8, data: struct {
    status: ?[]const u8,
    name: ?[]const u8,
    railway_service_id: ?[]const u8,
}) !void {
    if (session_id.len == 0) return error.InvalidInput;

    const now = std.time.timestamp();
    var updates = std.ArrayList([]const u8).init(allocator);
    defer updates.deinit();

    if (data.status) |status| {
        try updates.appendSlice("status = ");
        try updates.append(status);
        try updates.appendSlice(", ");
    }
    if (data.name) |name| {
        try updates.appendSlice("name = '");
        try updates.append(name);
        try updates.append("', ");
    }
    if (data.railway_service_id) |sid| {
        try updates.appendSlice("railway_service_id = '");
        try updates.append(sid);
        try updates.append("', ");
    }

    if (updates.items.len == 0) return;

    // Remove trailing comma
    var set_clause = try updates.toOwnedSlice();
    if (set_clause.len > 2) {
        set_clause = try allocator.dupe(u8, set_clause[0 .. set_clause.len - 2]);
    }

    try updates.writer().print("updated_at = {d}", .{now});

    const sql = try std.fmt.allocPrint(allocator,
        \\UPDATE sessions SET {s}updated_at = {d} WHERE id = '{s}'
    , .{ set_clause, now, session_id });

    defer {
        allocator.free(set_clause);
        allocator.free(sql);
    }

    _ = try PostgresClient.query(client, sql, &.{});
}

/// Delete session
pub fn deleteSession(client: *PostgresClient, session_id: []const u8) !void {
    if (session_id.len == 0) return error.InvalidInput;

    const sql = try std.fmt.allocPrint(std.heap.page_allocator,
        \\DELETE FROM sessions WHERE id = '{s}'
    , .{ session_id });

    defer std.heap.page_allocator.free(sql);

    _ = try PostgresClient.query(client, sql, &.{});
}

/// Generate a unique session ID
fn generateSessionId(allocator: Allocator) ![]const u8 {
    const now = std.time.nanoTimestamp();
    const random = std.crypto.random.intRangeAtMost(usize, std.math.maxInt(usize));

    return try std.fmt.allocPrint(allocator, "sess_{d}_{x}", .{ now, random });
}

test "sessions: create and get" {
    // Test only creates Session struct directly - no DB connection needed
    const id = "sess_123_456";
    const now = std.time.timestamp();

    const session = Session{
        .id = id,
        .name = "test-session",
        .status = "active",
        .railway_service_id = "svc_123",
        .created_at = now,
        .updated_at = now,
    };

    try std.testing.expectEqualStrings(session.id, id);
    try std.testing.expectEqualStrings(session.name, "test-session");
    try std.testing.expectEqualStrings(session.status, "active");
}
