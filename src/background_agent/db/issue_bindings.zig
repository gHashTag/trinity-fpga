//! Issue Bindings Registry — Issue ↔ Session ↔ Service ↔ Soul
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const Allocator = std.mem.Allocator;

/// Issue binding structure
pub const IssueBinding = struct {
    issue_number: u32,
    agent_id: []const u8,
    soul_file: []const u8,
    session_id: []const u8,
    railway_service_id: []const u8,
    deployment_id: []const u8,
    experience_file: []const u8,
    status: []const u8,
};

/// Bindings file structure
pub const BindingsFile = struct {
    bindings: std.ArrayList(IssueBinding),
    version: []const u8,
    last_updated: i64,
};

/// Bindings error
pub const BindingsError = error{
    FileNotFound,
    InvalidJson,
    BindingNotFound,
    InvalidStatus,
};

/// Valid statuses
pub const Status = struct {
    const ACTIVE = "ACTIVE";
    const STOPPED = "STOPPED";
    const FAILED = "FAILED";
};

/// Load bindings from file
pub fn loadBindings(allocator: Allocator) !BindingsFile {
    const file_path = ".trinity/issue_bindings.json";

    const file = std.fs.cwd().openFile(file_path, .{}) catch |err| switch (err) {
        error.FileNotFound => return error.FileNotFound,
        else => return err,
    };
    defer file.close();

    const content = try file.readToEndAlloc(allocator);
    defer allocator.free(content);

    var parsed = try std.json.parseFromSlice(allocator, content);
    defer parsed.deinit();

    const root_obj = parsed.root.object;
    const version = try root_obj.get("version");
    const last_updated = try root_obj.get("last_updated");

    const bindings_array = try root_obj.get("bindings");
    const bindings = try bindings_array.array;

    var bindings_list = std.ArrayList(IssueBinding).init(allocator);

    for (bindings.items) |binding_obj| {
        const issue_num = try binding_obj.object.get("issue_number");
        const agent_id = try binding_obj.object.get("agent_id");
        const soul_file = try binding_obj.object.get("soul_file");
        const session_id = try binding_obj.object.get("session_id");
        const railway_service_id = try binding_obj.object.get("railway_service_id");
        const deployment_id = try binding_obj.object.get("deployment_id");
        const experience_file = try binding_obj.object.get("experience_file");
        const status = try binding_obj.object.get("status");

        try bindings_list.append(IssueBinding{
            .issue_number = @intCast(issue_num.integer),
            .agent_id = try allocator.dupe(u8, agent_id.string),
            .soul_file = try allocator.dupe(u8, soul_file.string),
            .session_id = try allocator.dupe(u8, session_id.string),
            .railway_service_id = try allocator.dupe(u8, railway_service_id.string),
            .deployment_id = try allocator.dupe(u8, deployment_id.string),
            .experience_file = try allocator.dupe(u8, experience_file.string),
            .status = try allocator.dupe(u8, status.string),
        });
    }

    return BindingsFile{
        .bindings = bindings_list,
        .version = try allocator.dupe(u8, version.string),
        .last_updated = @intCast(last_updated.integer),
    };
}

/// Save bindings to file
pub fn saveBindings(allocator: Allocator, bindings_file: *BindingsFile) !void {
    const file_path = ".trinity/issue_bindings.json";

    var bindings = std.ArrayList(std.json.Value).init(allocator);
    defer bindings.deinit();

    for (bindings_file.bindings.items) |binding| {
        var binding_obj = std.json.ObjectMap.init(allocator);
        defer binding_obj.deinit();

        try binding_obj.put("issue_number", std.json.Value{ .integer = @intCast(binding.issue_number) });
        try binding_obj.put("agent_id", std.json.Value{ .string = binding.agent_id });
        try binding_obj.put("soul_file", std.json.Value{ .string = binding.soul_file });
        try binding_obj.put("session_id", std.json.Value{ .string = binding.session_id });
        try binding_obj.put("railway_service_id", std.json.Value{ .string = binding.railway_service_id });
        try binding_obj.put("deployment_id", std.json.Value{ .string = binding.deployment_id });
        try binding_obj.put("experience_file", std.json.Value{ .string = binding.experience_file });
        try binding_obj.put("status", std.json.Value{ .string = binding.status });

        try bindings.append(std.json.Value{ .object = binding_obj });
    }

    var root_obj = std.json.ObjectMap.init(allocator);
    defer root_obj.deinit();

    try root_obj.put("bindings", std.json.Value{ .array = bindings.toOwnedSlice() });
    try root_obj.put("version", std.json.Value{ .string = bindings_file.version });
    try root_obj.put("last_updated", std.json.Value{ .integer = std.time.timestamp() });

    const json_string = try std.json.stringifyAlloc(allocator, std.json.Value{ .object = root_obj }, .{ .whitespace = .indent });
    defer allocator.free(json_string);

    try std.fs.cwd().writeFile(.{
        .sub_path = file_path,
        .data = json_string,
    });
}

/// Find binding by issue number
pub fn findBinding(bindings_file: *BindingsFile, issue_number: u32) !*IssueBinding {
    for (bindings_file.bindings.items) |*binding| {
        if (binding.issue_number == issue_number) {
            return binding;
        }
    }
    return error.BindingNotFound;
}

/// Add or update binding
pub fn upsertBinding(allocator: Allocator, bindings_file: *BindingsFile, binding: IssueBinding) !void {
    // Remove existing binding if found
    var i: usize = 0;
    while (i < bindings_file.bindings.items.len) : (i += 1) {
        if (bindings_file.bindings.items[i].issue_number == binding.issue_number) {
            bindings_file.bindings.orderedRemove(i);
            break;
        }
    }

    try bindings_file.bindings.append(binding);
}

/// Remove binding by issue number
pub fn removeBinding(bindings_file: *BindingsFile, issue_number: u32) !void {
    var i: usize = 0;
    while (i < bindings_file.bindings.items.len) : (i += 1) {
        if (bindings_file.bindings.items[i].issue_number == issue_number) {
            bindings_file.bindings.orderedRemove(i);
            return;
        }
    }
    return error.BindingNotFound;
}

/// Update binding status
pub fn updateBindingStatus(bindings_file: *BindingsFile, issue_number: u32, status: []const u8) !void {
    for (bindings_file.bindings.items) |*binding| {
        if (binding.issue_number == issue_number) {
            // Create new binding with updated status
            var new_binding = binding.*;
            new_binding.status = status;
            return;
        }
    }
    return error.BindingNotFound;
}

test "issue_bindings: load and save" {
    const allocator = std.testing.allocator;

    // Test file structure
    const content = "{\"bindings\":[{\"issue_number\":505,\"agent_id\":\"ralph-505-a1\",\"soul_file\":\".trinity/souls/issue-505/SOUL.md\",\"session_id\":\"sess_123\",\"railway_service_id\":\"svc_abc\",\"deployment_id\":\"dep_xyz\",\"experience_file\":\".trinity/experience/issue-505-run-001.jsonl\",\"status\":\"ACTIVE\"}],\"version\":\"1.0.0\",\"last_updated\":1234567890}";

    const file = try std.fs.cwd().makeOpenPath("test_bindings.json", .{ .read = false });
    defer file.close();

    try file.writeAll(content);

    // Parse and verify
    const bindings = try loadBindings(allocator);
    defer {
        for (bindings.bindings.items) |*b| {
            allocator.free(b.agent_id);
            allocator.free(b.soul_file);
            allocator.free(b.session_id);
            allocator.free(b.railway_service_id);
            allocator.free(b.deployment_id);
            allocator.free(b.experience_file);
            allocator.free(b.status);
        }
        bindings.bindings.deinit();
        allocator.free(bindings.version);
    }

    try std.testing.expectEqual(bindings.bindings.items.len, 1);
    try std.testing.expectEqual(bindings.bindings.items[0].issue_number, 505);
    try std.testing.expectEqualStrings(bindings.bindings.items[0].status, "ACTIVE");

    std.fs.cwd().deleteFile("test_bindings.json") catch {};
}
