//! Background Agent API - Main Entrypoint
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");

const Config = @import("./config.zig").Config;
const loadConfig = @import("./config.zig").loadConfig;
const Server = @import("./server.zig").Server;
const PostgresClient = @import("./db/client.zig").PostgresClient;

const allocator = std.heap.page_allocator;

pub fn main() !u8 {
    // Load configuration
    const config = try loadConfig(allocator);
    std.log.info("Loaded config: port={}, local_mode={}", .{ config.port, config.localMode });

    // Initialize database client
    var db_client = PostgresClient{
        .allocator = allocator,
    };

    if (!config.localMode) {
        try PostgresClient.connect(&db_client, config.databaseUrl);
        std.log.info("Connected to database");
    } else {
        std.log.info("Running in local mode - no database connection");
    }

    defer PostgresClient.close(&db_client);

    // Initialize server
    var server = try Server.init(allocator, config, db_client, config.authSecret);
    defer server.stop();

    // Start server
    try server.start();

    return 0;
}
