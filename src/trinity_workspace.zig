//! Single workspace root for `.trinity/` state: walk up from cwd until `build.zig`
//! is found, then `chdir` there. Prevents `src/.trinity`, `fpga/.trinity`, etc.
//!
//! Override: absolute path in `TRINITY_REPO_ROOT` (directory that contains `.trinity/`).
//!
//! Zig 0.16 note: every stdlib replacement for what this file used to call --
//! `std.process.setCurrentPath`, `std.Io.Dir.cwd().realPathFile`,
//! `std.Io.Dir.accessAbsolute` -- now takes an `Io`, and `std.process.getEnvVarOwned`
//! and `std.posix.getenv` are gone outright. build.zig declares this file as a
//! module with no imports, so the tri_io/tri_env shims are not reachable from
//! here and there is no Io to be had. getcwd/chdir/access/getenv are precisely
//! the four libc calls the removed 0.15 functions made underneath, so they are
//! declared directly -- the same route `src/tri/tri_env.zig` takes for getenv.

const std = @import("std");

const c = struct {
    extern "c" fn getenv(name: [*:0]const u8) ?[*:0]const u8;
    extern "c" fn getcwd(buf: [*]u8, size: usize) ?[*:0]u8;
    extern "c" fn chdir(path: [*:0]const u8) c_int;
    extern "c" fn access(path: [*:0]const u8, mode: c_int) c_int;
};

/// `access` mode bit: test for existence only.
const F_OK: c_int = 0;

/// Best-effort: never fail startup if discovery fails (stay in cwd).
pub fn cdToRepoRootSilent() void {
    cdToRepoRoot() catch {};
}

pub fn cdToRepoRoot() !void {
    if (c.getenv("TRINITY_REPO_ROOT")) |root| {
        if (c.chdir(root) != 0) return error.ChangeDirFailed;
        return;
    }

    // The walk appends "/build.zig" in place and every libc call here wants a
    // NUL terminator, so the buffer carries one byte of headroom past a path.
    var scratch: [std.Io.Dir.max_path_bytes]u8 = undefined;
    const cwd = c.getcwd(&scratch, scratch.len) orelse return error.CurrentPathUnavailable;
    var cur_len = std.mem.span(cwd).len;

    while (cur_len > 0) {
        const cur = scratch[0..cur_len];
        const sep_len = std.fs.path.sep_str.len;
        const need = cur.len + sep_len + "build.zig".len;
        if (need + 1 > scratch.len) return error.NameTooLong;
        @memcpy(scratch[cur.len..][0..sep_len], std.fs.path.sep_str);
        @memcpy(scratch[cur.len + sep_len ..][0.."build.zig".len], "build.zig");
        scratch[need] = 0;
        const probe: [:0]const u8 = scratch[0..need :0];
        if (c.access(probe, F_OK) == 0) {
            // Cut the probe suffix back off and chdir to the directory itself.
            scratch[cur_len] = 0;
            const dir: [:0]const u8 = scratch[0..cur_len :0];
            if (c.chdir(dir) != 0) return error.ChangeDirFailed;
            return;
        }
        const parent = std.fs.path.dirname(cur) orelse return;
        if (parent.len == cur.len) return;
        cur_len = parent.len;
    }
}
