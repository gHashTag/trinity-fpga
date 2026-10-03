//! Single workspace root for `.trinity/` state: walk up from cwd until `build.zig`
//! is found, then `chdir` there. Prevents `src/.trinity`, `fpga/.trinity`, etc.
//!
//! Override: absolute path in `TRINITY_REPO_ROOT` (directory that contains `.trinity/`).
//!
//! Zig 0.16: the stdlib replacements for what this file calls all take an `Io`
//! (`std.process.currentPath`, `std.process.setCurrentPath`,
//! `std.Io.Dir.accessAbsolute`), and `std.process.getEnvVarOwned` is gone
//! outright. build.zig now declares the tri_io/tri_env shims on this module
//! (#767), so the Io comes from `tri_io.get()` — which builds its own fallback
//! Io when no main has installed one — and the environment from `tri_env`.
//! The four libc externs the previous version declared are gone.

const std = @import("std");
const tri_io = @import("tri_io");
const tri_env = @import("tri_env");

/// Best-effort: never fail startup if discovery fails (stay in cwd).
pub fn cdToRepoRootSilent() void {
    cdToRepoRoot() catch {};
}

pub fn cdToRepoRoot() !void {
    const io = tri_io.get();

    if (tri_env.getPosix("TRINITY_REPO_ROOT")) |root| {
        try std.process.setCurrentPath(io, root);
        return;
    }

    // The walk appends "/build.zig" in place for the access probe, so the
    // buffer carries one byte of headroom past a path.
    var scratch: [std.Io.Dir.max_path_bytes]u8 = undefined;
    const cwd_len = try std.process.currentPath(io, &scratch);
    var cur_len = cwd_len;

    while (cur_len > 0) {
        const cur = scratch[0..cur_len];
        const sep_len = std.fs.path.sep_str.len;
        const need = cur.len + sep_len + "build.zig".len;
        if (need + 1 > scratch.len) return error.NameTooLong;
        @memcpy(scratch[cur.len..][0..sep_len], std.fs.path.sep_str);
        @memcpy(scratch[cur.len + sep_len ..][0.."build.zig".len], "build.zig");
        const probe = scratch[0..need];
        if (std.Io.Dir.accessAbsolute(io, probe, .{})) |_| {
            // Cut the probe suffix back off and chdir to the directory itself.
            const dir = scratch[0..cur_len];
            try std.process.setCurrentPath(io, dir);
            return;
        } else |_| {}

        const parent = std.fs.path.dirname(cur) orelse return;
        if (parent.len == cur.len) return;
        cur_len = parent.len;
    }
}
