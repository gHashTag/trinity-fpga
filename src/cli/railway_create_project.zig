// Railway: Create project via GraphQL
const std = @import("std");

pub fn main() !void {
    var gpa = std.heap.DebugAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const args = try std.process.argsAlloc(allocator);
    defer std.process.argsFree(allocator, args);

    if (args.len < 2) {
        std.debug.print("Usage: railway-create-project <token>\n", .{});
        std.process.exit(1);
    }

    const token = args[1];

    const query =
        \\{"query": "mutation($input: ProjectCreateInput!) { projectCreate(input: $input) { id name } }", "variables": {"input": {"name": "Trinity Farm 9"}}}
    ;

    std.debug.print("🔧 Creating Railway project...\n", .{});

    const auth_header = try std.fmt.allocPrint(allocator, "Authorization: Bearer {s}", .{token});
    defer allocator.free(auth_header);

    const result = try std.process.Child.run(.{
        .allocator = allocator,
        .argv = &.{ "curl", "-s", "-X", "POST", "-H", auth_header, "-H", "Content-Type: application/json", "-d", query, "https://backboard.railway.com/graphql" },
    });
    defer allocator.free(result.stderr);

    std.debug.print("{s}\n", .{result.stdout});

    // Match the sibling railway_* tools: fail with a non-zero exit instead of
    // silently succeeding on a failed request or a GraphQL error, so scripts
    // and CI can detect a project that wasn't actually created.
    if (result.term.Exited != 0) return error.RequestFailed;
    if (std.mem.indexOf(u8, result.stdout, "\"errors\"") != null) {
        return error.ApiError;
    }
}
