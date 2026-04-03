const std = @import("std");

pub fn main() !void {
    const alloc = std.heap.page_allocator;

    const build_dir = "deploy/railway-background-agent";

    // Create/clean build directory
    try std.fs.cwd().deleteTree(build_dir);
    try std.fs.cwd().makePath(build_dir ++ "/src");

    const essential_files = [_][]const u8{
        "build.zig",
        "src/background_agent",
        "src/vsa",
        "src/vm.zig",
        "src/hybrid.zig",
        "src/c_api.zig",
        "src/science.zig",
        "src/vsa_jit.zig",
    };

    inline for (essential_files) |file| {
        const src = std.fs.path.join(alloc, &.{".", file}) catch return error.JoinFailed;
        const dst = std.fs.path.join(alloc, &.{build_dir, file}) catch return error.JoinFailed;
        try copyRecursive(alloc, src, dst);
    }

    // Copy Dockerfile and config
    try std.fs.cwd().copyFile(
        "deploy/railway-background-agent",
        "Dockerfile",
        std.fs.cwd(),
        build_dir ++ "/Dockerfile",
        .{},
    );
    try std.fs.cwd().copyFile(
        "deploy/railway-background-agent",
        "railway.json",
        std.fs.cwd(),
        build_dir ++ "/railway.json",
        .{},
    );

    std.log.info("Minimal deployment ready in {s}", .{build_dir});
    std.log.info("Run: cd {s} && railway up", .{build_dir});
}

fn copyRecursive(alloc: std.mem.Allocator, src: []const u8, dst: []const u8) !void {
    const src_stat = try std.fs.cwd().statFile(src);

    if (src_stat.kind == .directory) {
        try std.fs.cwd().makePath(dst);
        var dir = try std.fs.cwd().openDir(src, .{ .iterate = true });

        var iter = dir.iterate();
        while (try iter.next()) |entry| {
            const src_path = try std.fs.path.join(alloc, &.{ src, entry.name });
            const dst_path = try std.fs.path.join(alloc, &.{ dst, entry.name });
            try copyRecursive(alloc, src_path, dst_path);
        }
    } else {
        const src_dir_name = std.fs.path.dirname(src) orelse ".";
        const src_file_name = std.fs.path.basename(src);
        const dst_dir_name = std.fs.path.dirname(dst) orelse ".";
        const dst_file_name = std.fs.path.basename(dst);
        const src_dir = std.fs.cwd().openDir(src_dir_name, .{}) catch return error.OpenFailed;
        defer src_dir.close();
        const dst_dir = std.fs.cwd().openDir(dst_dir_name, .{}) catch return error.OpenFailed;
        defer dst_dir.close();
        try src_dir.copyFile(src_file_name, dst_dir, dst_file_name, .{});
    }
}
