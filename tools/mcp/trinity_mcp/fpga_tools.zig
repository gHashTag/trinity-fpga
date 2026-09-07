// @origin(spec:fpga_tools.tri) @regen(manual-impl)
//! FPGA TOOLS — MCP Tool Module for FPGA UART Bridge
//! Shells out to `tri fpga uart` CLI commands.
//! φ² + 1/φ² = 3 | TRINITY
// @origin(manual) @regen(pending)

const std = @import("std");
const tri_io = @import("tri_io");
const tri_proc = @import("tri_proc");

const MAX_OUTPUT = 8192;

// ═══════════════════════════════════════════════════════════════════════════════
// PUBLIC API — called from server.zig handleFpgaTool()
// ═══════════════════════════════════════════════════════════════════════════════

pub fn fpgaUartScan(buf: *[MAX_OUTPUT]u8) []const u8 {
    return runTriFpga(buf, &.{ "uart", "scan" });
}

pub fn fpgaUartPing(buf: *[MAX_OUTPUT]u8, device: []const u8) []const u8 {
    if (device.len > 0) {
        return runTriFpga(buf, &.{ "uart", "ping", device });
    }
    return runTriFpga(buf, &.{ "uart", "ping" });
}

pub fn fpgaUartSend(buf: *[MAX_OUTPUT]u8, device: []const u8, hex_bytes: []const u8) []const u8 {
    if (device.len > 0) {
        return runTriFpga(buf, &.{ "uart", "send", device, hex_bytes });
    }
    return runTriFpga(buf, &.{ "uart", "send", hex_bytes });
}

// ═══════════════════════════════════════════════════════════════════════════════
// INTERNAL — shell out to tri fpga
// ═══════════════════════════════════════════════════════════════════════════════

fn runTriFpga(buf: *[MAX_OUTPUT]u8, args: []const []const u8) []const u8 {
    var argv: [16][]const u8 = undefined;
    argv[0] = TRI_PATH;
    argv[1] = "fpga";
    const n = @min(args.len, 14);
    for (0..n) |i| {
        argv[2 + i] = args[i];
    }

    // 0.16 removed Child.init/spawn/readToEndAlloc as a usable trio here, and
    // std.process.run does not search PATH; tri_proc.run does both and collapses
    // the old spawn/read/wait dance into one call.
    const gpa = std.heap.page_allocator;
    const result = tri_proc.run(.{
        .allocator = gpa,
        .argv = argv[0 .. 2 + n],
        .max_output_bytes = MAX_OUTPUT,
    }) catch |err| {
        return copyToBuf(buf, switch (err) {
            error.FileNotFound => "Error: tri binary not found (run zig build)",
            else => "Error: Failed to spawn tri fpga process",
        });
    };
    defer gpa.free(result.stdout);
    defer gpa.free(result.stderr);

    // The old child inherited stderr, so its diagnostics reached this process's
    // stderr. `run` captures it instead, so forward it to keep that visible --
    // stdout here is the MCP protocol channel and must not carry it.
    if (result.stderr.len > 0) {
        std.Io.File.stderr().writeStreamingAll(tri_io.get(), result.stderr) catch {};
    }

    if (result.stdout.len == 0) {
        return copyToBuf(buf, "OK (no output — check stderr)");
    }

    const len = @min(result.stdout.len, MAX_OUTPUT);
    @memcpy(buf[0..len], result.stdout[0..len]);
    return buf[0..len];
}

fn copyToBuf(buf: *[MAX_OUTPUT]u8, msg: []const u8) []const u8 {
    const len = @min(msg.len, MAX_OUTPUT);
    @memcpy(buf[0..len], msg[0..len]);
    return buf[0..len];
}

const TRI_PATH = "zig-out/bin/tri";
