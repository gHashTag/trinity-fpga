//! Agent Commands — tri agent spawn/run/stop
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const Allocator = std.mem.Allocator;

const RailwayClient = @import("../background_agent/railway/client.zig").RailwayClient;
const issue_bindings = @import("../background_agent/db/issue_bindings.zig");
const sessions = @import("../background_agent/db/sessions.zig");

/// Run agent spawn command
pub fn runAgentSpawnCommand(allocator: Allocator, args: []const []const u8) !void {
    if (args.len < 2) {
        std.debug.print("Usage: tri agent spawn <issue_number>\n", .{});
        return error.InvalidInput;
    }

    const issue_str = args[1];
    const issue_number = std.fmt.parseInt(u32, issue_str, 10) catch |err| {
        std.debug.print("Invalid issue number: {s} ({any})\n", .{ issue_str, err });
        return error.InvalidInput;
    };

    try spawnAgent(allocator, issue_number);
}

/// Spawn agent for given issue
pub fn spawnAgent(allocator: Allocator, issue_number: u32) !void {
    const print = std.debug.print;

    // 1. Load existing bindings
    var bindings_file = issue_bindings.loadBindings(allocator) catch |err| {
        print("Failed to load bindings: {any}\n", .{err});
        return err;
    };
    defer {
        for (bindings_file.bindings.items) |*b| {
            allocator.free(b.agent_id);
            allocator.free(b.soul_file);
            allocator.free(b.session_id);
            allocator.free(b.railway_service_id);
            allocator.free(b.deployment_id);
            allocator.free(b.experience_file);
            allocator.free(b.status);
        }
        bindings_file.bindings.deinit();
        allocator.free(bindings_file.version);
    }

    // 2. Check if binding already exists
    if (issue_bindings.findBinding(&bindings_file, issue_number)) |_| {
        print("Issue {d} already has an active binding\n", .{issue_number});
        const binding = try issue_bindings.findBinding(&bindings_file, issue_number);
        print("  Agent ID: {s}\n", .{binding.?.agent_id});
        print("  Status: {s}\n", .{binding.?.status});
        return error.InvalidInput;
    } else |_| {};

    // 3. Generate agent ID
    const agent_id = try generateAgentId(allocator, issue_number);
    defer allocator.free(agent_id);

    // 4. Create soul file directory and content
    const soul_dir = try std.fmt.allocPrint(allocator, ".trinity/souls/issue-{d}-{s}", .{ issue_number, agent_id });
    defer allocator.free(soul_dir);

    try std.fs.cwd().makePath(soul_dir);

    const soul_path = try std.fmt.allocPrint(allocator, "{s}/SOUL.md", .{ soul_dir });
    defer allocator.free(soul_path);

    const soul_content = try generateSoulContent(allocator, issue_number, agent_id);
    defer allocator.free(soul_content);

    try std.fs.cwd().writeFile(.{
        .sub_path = soul_path,
        .data = soul_content,
    });

    print("Created SOUL.md: {s}\n", .{soul_path});

    // 5. Create Railway service
    // TODO: Implement Railway service creation
    const service_id = ""; // Placeholder

    // 6. Create session
    const session_name = try std.fmt.allocPrint(allocator, "issue-{d}", .{ issue_number });
    defer allocator.free(session_name);

    const session = try sessions.createSession(allocator, undefined, session_name, service_id);
    print("Created session: {s}\n", .{session.id});

    // 7. Create binding
    const binding = issue_bindings.IssueBinding{
        .issue_number = issue_number,
        .agent_id = try allocator.dupe(u8, agent_id),
        .soul_file = try allocator.dupe(u8, soul_path),
        .session_id = try allocator.dupe(u8, session.id),
        .railway_service_id = try allocator.dupe(u8, service_id),
        .deployment_id = try allocator.dupe(u8, ""),
        .experience_file = try allocator.dupe(u8, ""),
        .status = try allocator.dupe(u8, issue_bindings.Status.ACTIVE),
    };
    defer {
        allocator.free(binding.agent_id);
        allocator.free(binding.soul_file);
        allocator.free(binding.session_id);
        allocator.free(binding.railway_service_id);
        allocator.free(binding.deployment_id);
        allocator.free(binding.experience_file);
        allocator.free(binding.status);
    }

    try issue_bindings.upsertBinding(allocator, &bindings_file, binding);

    // 8. Save bindings
    bindings_file.last_updated = std.time.timestamp();
    try issue_bindings.saveBindings(allocator, &bindings_file);

    print("Created binding for issue {d}\n", .{issue_number});
    print("  Agent: {s}\n", .{agent_id});
    print("  Soul: {s}\n", .{soul_path});
    print("  Session: {s}\n", .{session.id});

    // TODO: Post GitHub comment: 🚀 [SANDBOX] Created container/service for issue #{d}
}

/// Generate unique agent ID
fn generateAgentId(allocator: Allocator, issue_number: u32) ![]const u8 {
    const now = std.time.nanoTimestamp();
    const random = std.crypto.random.intRangeAtMost(usize, std.math.maxInt(usize));

    return try std.fmt.allocPrint(allocator, "issue-{d}-a1_{d}_{x}", .{ issue_number, now, random });
}

/// Generate SOUL.md content for new agent
fn generateSoulContent(allocator: Allocator, issue_number: u32, agent_id: []const u8) ![]const u8 {
    return try std.fmt.allocPrint(allocator,
        \\# SOUL.md — Agent Soul Binding
        \\
        \\**Law**: Every container/agent MUST have `SOUL.md` at root.
        \\
        \\---
        \\
        \\## Agent Identity
        \\
        \\| Field | Value |
        \\|-------|--------|
        \\| **Agent Type** | Ralph (default) |
        \\| **Agent ID** | {s} |
        \\| **Bound Issue** | #{d} |
        \\
        \\---
        \\
        \\## Mission
        \\
        \\```markdown
        \\Resolve issue #{d}
        \\```
        \\
        \\---
        \\
        \\## Allowed Commands
        \\
        \\```markdown
        \\Commands this agent is permitted to execute:
        \\
        \\- `tri dev scan` — Read issues + experience
        \\- `tri dev pick --smart` — Priority + MNL selection
        \\- `tri spec create` — Create .tri spec from experience
        \\- `tri gen` — Generate .t27 + .zig from .tri
        \\- `tri test` — Compare outputs, verify
        \\- `tri verdict --toxic` — Toxic verdict with MNL
        \\- `tri experience save` — Save episode + learnings
        \\- `tri git commit` — Commit changes
        \\- `tri loop decide` — Continue or stop?
        \\
        \\Command execution MUST follow CLAUDE.md law.
        \\```
        \\
        \\---
        \\
        \\## Stop Conditions
        \\
        \\```markdown
        \\Conditions that cause this agent to stop:
        \\
        \\1. Task completed successfully (all 8 steps finished)
        \\2. 3 consecutive failures on same step (toxic pattern detected)
        \\3. Manual stop signal received
        \\4. Issue closed by user
        \\```
        \\
        \\---
        \\
        \\## Reporting Format
        \\
        \\```markdown
        \\How this agent reports progress:
        \\
        \\**Protocol v2 Comment Format:**
        \\- `🔍 [RESEARCH] Step 1/8 — Scanning issues...`
        \\- `📜 [SPEC] Reused nearest template from .trinity/experience/`
        \\- `⚙️ [CODEGEN] .tri -> .zig via tri gen`
        \\- `🧪 [TEST] 6/7 tests passing`
        \\- `☣️ [VERDICT] Past: 3/7. Now: 7/7`
        \\- `✅ [DONE] Build clean. Commit pushed`
        \\
        \\All significant steps MUST be reflected as GitHub issue comments.
        \\```
        \\
        \\---
        \\
        \\## References
        \\
        \\- **CLAUDE.md** — Trinity project laws and rules
        \\- **AGENTS.md** — Agent swarm documentation
        \\- **Protocol v2** — Comment formatting specification
        \\
        \\---
        \\
        \\**Created by**: `tri agent spawn {d}`
        \\**Active until**: Issue closed or agent stopped
    , .{ agent_id, issue_number });
}

/// Run agent run command
pub fn runAgentRunCommand(allocator: Allocator, args: []const []const u8) !void {
    if (args.len < 2) {
        std.debug.print("Usage: tri agent run <issue_number>\n", .{});
        return error.InvalidInput;
    }

    const issue_str = args[1];
    const issue_number = std.fmt.parseInt(u32, issue_str, 10) catch |err| {
        std.debug.print("Invalid issue number: {s} ({any})\n", .{ issue_str, err });
        return error.InvalidInput;
    };

    std.debug.print("Starting agent run for issue {d}...\n", .{issue_number});
    std.debug.print("TODO: Implement full 8-step cycle\n", .{});
}

/// Run agent stop command
pub fn runAgentStopCommand(allocator: Allocator, args: []const []const u8) !void {
    if (args.len < 2) {
        std.debug.print("Usage: tri agent stop <issue_number>\n", .{});
        return error.InvalidInput;
    }

    const issue_str = args[1];
    const issue_number = std.fmt.parseInt(u32, issue_str, 10) catch |err| {
        std.debug.print("Invalid issue number: {s} ({any})\n", .{ issue_str, err });
        return error.InvalidInput;
    };

    // 1. Load bindings
    var bindings_file = issue_bindings.loadBindings(allocator) catch |err| {
        std.debug.print("Failed to load bindings: {any}\n", .{err});
        return err;
    };
    defer {
        for (bindings_file.bindings.items) |*b| {
            allocator.free(b.agent_id);
            allocator.free(b.soul_file);
            allocator.free(b.session_id);
            allocator.free(b.railway_service_id);
            allocator.free(b.deployment_id);
            allocator.free(b.experience_file);
            allocator.free(b.status);
        }
        bindings_file.bindings.deinit();
        allocator.free(bindings_file.version);
    }

    // 2. Find binding
    const binding = try issue_bindings.findBinding(&bindings_file, issue_number);
    if (binding.railway_service_id.len == 0) {
        std.debug.print("Issue {d} has no associated Railway service\n", .{issue_number});
        return error.BindingNotFound;
    }

    // 3. Delete Railway service
    // TODO: Implement Railway service deletion
    std.debug.print("Would delete service: {s}\n", .{binding.railway_service_id});

    // 4. Update binding status
    try issue_bindings.updateBindingStatus(&bindings_file, issue_number, issue_bindings.Status.STOPPED);
    bindings_file.last_updated = std.time.timestamp();
    try issue_bindings.saveBindings(allocator, &bindings_file);

    std.debug.print("Stopped agent for issue {d}\n", .{issue_number});
    std.debug.print("  Agent: {s}\n", .{binding.agent_id});

    // TODO: Post GitHub comment: 🛑 [SANDBOX] Stopped container for issue #{d}
}

test "agent_commands: generate agent id" {
    const allocator = std.testing.allocator;
    const agent_id = try generateAgentId(allocator, 505);
    defer allocator.free(agent_id);

    try std.testing.expect(std.mem.startsWith(u8, agent_id, "issue-505-"));
    try std.testing.expect(std.mem.indexOf(u8, agent_id, "a1_") != null);
}
