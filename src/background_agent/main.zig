//! Background Agent API - Main Entrypoint
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");

const Config = @import("./config.zig").Config;
const loadConfig = @import("./config.zig").loadConfig;
const server_module = @import("./server.zig");
const serverStart = @import("./server.zig").start;
const serverStop = @import("./server.zig").stop;
const PostgresClient = @import("./db/client.zig").PostgresClient;

const allocator = std.heap.page_allocator;

pub fn main() !u8 {
    // Load configuration
    const config = try loadConfig(allocator);
    std.log.info("Loaded config: port={}, local_mode={}", .{ config.port, config.localMode });

    // Initialize database client
    var db_client = PostgresClient{
        .allocator = allocator,
        .stream = null,
    };

    if (!config.localMode) {
        try PostgresClient.connect(&db_client, config.databaseUrl);
        std.log.info("Connected to database", .{});
    } else {
        std.log.info("Running in local mode - no database connection", .{});
    }

    defer PostgresClient.close(&db_client);

    // Initialize server
    var server = try server_module.init(allocator, config, db_client, config.authSecret);
    defer serverStop(&server);

    // Start server
    try serverStart(&server);

    return 0;
}
