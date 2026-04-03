//! Railway GraphQL Client
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const Allocator = std.mem.Allocator;
const net = std.net;

/// Railway GraphQL endpoint
pub const RAILWAY_GRAPHQL_URL = "https://backboard.railway.app/graphql/v2";

/// Railway service input
pub const ServiceCreateInput = struct {
    projectId: []const u8,
    environmentId: []const u8,
    name: []const u8,
    image: []const u8,
};

/// Service create response
pub const ServiceCreateResponse = struct {
    id: []const u8,
};

/// Service delete response
pub const ServiceDeleteResponse = struct {
    serviceId: []const u8,
};

/// Railway error
pub const Error = error{
    ConnectionFailed,
    InvalidResponse,
    AuthFailed,
    GraphQL
};

/// Railway client
pub const RailwayClient = struct {
    allocator: Allocator,
    api_token: []const u8,
    project_id: []const u8,
};

/// Initialize Railway client
pub fn init(allocator: Allocator, api_token: []const u8, project_id: []const u8) RailwayClient {
    return RailwayClient{
        .allocator = allocator,
        .api_token = api_token,
        .project_id = project_id,
    };
}

/// Create a Railway service
pub fn createService(client: *RailwayClient, environment_id: []const u8, name: []const u8, image: []const u8) !ServiceCreateResponse {
    const input = ServiceCreateInput{
        .projectId = client.project_id,
        .environmentId = environment_id,
        .name = name,
        .image = image,
    };

    const mutation = try buildCreateServiceMutation(input);
    defer client.allocator.free(mutation);

    const response_body = try sendGraphQLRequest(client, mutation);
    defer client.allocator.free(response_body);

    return try parseServiceCreateResponse(client.allocator, response_body);
}

/// Delete a Railway service
pub fn deleteService(client: *RailwayClient, service_id: []const u8) !ServiceDeleteResponse {
    const mutation = try buildDeleteServiceMutation(service_id);
    defer client.allocator.free(mutation);

    const response_body = try sendGraphQLRequest(client, mutation);
    defer client.allocator.free(response_body);

    return try parseServiceDeleteResponse(client.allocator, response_body);
}

// ═══════════════════════════════════════════════════════════════════════════════
// INTERNAL: GraphQL Helpers
// ═════════════════════════════════════════════════════════════════════════════

/// Build serviceCreate mutation
fn buildCreateServiceMutation(input: ServiceCreateInput) ![]const u8 {
    _ = input;
    return std.fmt.allocPrint(std.heap.page_allocator,
        \\mutation {{ serviceCreate(input: $input: ServiceCreateInput!) {{ id }} }}
    );
}

/// Build serviceDelete mutation
fn buildDeleteServiceMutation(service_id: []const u8) ![]const u8 {
    return std.fmt.allocPrint(std.heap.page_allocator,
        \\mutation {{ serviceDelete(id: $id: String!) {{ serviceId }} }}
    , .{ service_id });
}

/// Send GraphQL request
fn sendGraphQLRequest(client: *RailwayClient, query: []const u8) ![]const u8 {
    // Build HTTP POST request
    var request = std.ArrayList(u8).init(std.heap.page_allocator);
    defer {
        const bytes = request.toOwnedSlice();
        std.heap.page_allocator.free(bytes);
    }

    try request.writer().print(
        \\POST {s} HTTP/1.1\r
        \\Host: backboard.railway.app\r
        \\Content-Type: application/json\r
        \\Content-Length: {d}\r
        \\Authorization: Bearer {s}\r
        \\Connection: close\r
        \\r
        \\{s}
    , .{ RAILWAY_GRAPHQL_URL, query.len, client.api_token, query });

    // Resolve address
    const address = try std.net.Address.parseIp("backboard.railway.app", 443);

    // Connect via TCP (HTTPS would need TLS)
    var stream = try net.tcpConnectToAddress(client.allocator, address);
    defer stream.close();

    // Send request
    _ = try stream.writeAll(request.items);

    // Read response
    var buffer: [16384]u8 = undefined;
    const response_len = try stream.read(&buffer);

    // Extract body (skip headers)
    const body_start = findBodyStart(buffer[0..response_len]);

    // Allocate and return body
    const body = try client.allocator.alloc(u8, response_len - body_start);
    @memcpy(body, buffer[body_start..response_len]);

    return body;
}

/// Find start of HTTP body (after double CRLF)
fn findBodyStart(data: []const u8) usize {
    var i: usize = 0;
    while (i + 3 < data.len) : (i += 1) {
        if (data[i] == '\r' and data[i + 1] == '\n' and data[i + 2] == '\r' and data[i + 3] == '\n') {
            return i + 4;
        }
    }
    return data.len;
}

/// Parse serviceCreate response
fn parseServiceCreateResponse(allocator: Allocator, body: []const u8) !ServiceCreateResponse {
    // Very simplified JSON parsing
    // Look for "data":{"serviceCreate":{"id":"..."}}
    const data_start = std.mem.indexOf(u8, body, "\"serviceCreate\"") orelse return error.InvalidResponse;
    const id_start = std.mem.indexOfPos(u8, body, data_start, "\"id\"") orelse return error.InvalidResponse;
    const id_value_start = id_start + 6; // Skip "id":"

    var id_end = id_value_start;
    while (id_end < body.len and body[id_end] != '"' and body[id_end] != '}') : (id_end += 1) {}

    const service_id = try allocator.dupe(u8, body[id_value_start..id_end]);

    return ServiceCreateResponse{ .id = service_id };
}

/// Parse serviceDelete response
fn parseServiceDeleteResponse(allocator: Allocator, body: []const u8) !ServiceDeleteResponse {
    // Look for "data":{"serviceDelete":{"serviceId":"..."}}
    const data_start = std.mem.indexOf(u8, body, "\"serviceDelete\"") orelse return error.InvalidResponse;
    const id_start = std.mem.indexOfPos(u8, body, data_start, "\"serviceId\"") orelse return error.InvalidResponse;
    const id_value_start = id_start + 13; // Skip "serviceId":"

    var id_end = id_value_start;
    while (id_end < body.len and body[id_end] != '"' and body[id_end] != '}') : (id_end += 1) {}

    const service_id = try allocator.dupe(u8, body[id_value_start..id_end]);

    return ServiceDeleteResponse{ .serviceId = service_id };
}

test "railway: build create mutation" {
    const input = ServiceCreateInput{
        .projectId = "proj_123",
        .environmentId = "env_456",
        .name = "test-service",
        .image = "nginx:latest",
    };

    const mutation = buildCreateServiceMutation(input);
    defer std.heap.page_allocator.free(mutation);

    try std.testing.expect(mutation.len > 0);
    try std.testing.expect(std.mem.indexOf(u8, mutation, "serviceCreate") != null);
}

test "railway: build delete mutation" {
    const mutation = buildDeleteServiceMutation("svc_789");
    defer std.heap.page_allocator.free(mutation);

    try std.testing.expect(mutation.len > 0);
    try std.testing.expect(std.mem.indexOf(u8, mutation, "serviceDelete") != null);
    try std.testing.expect(std.mem.indexOf(u8, mutation, "svc_789") != null);
}
