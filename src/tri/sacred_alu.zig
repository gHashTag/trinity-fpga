// @origin(spec:tri/sacred_alu.tri) @regen(manual-impl)
// Sacred ALU Command — FPGA GF16/TF3-9 Benchmark
//
// Usage: tri sacred [s|synth|bench] [module...]
//   s:  Synthesize Verilog modules
//   synth: Synthesize specific module
//   bench: Run benchmarks
//
// φ² + 1/φ² = 3 | TRINITY

const std = @import("std");

const tri_io = @import("tri_io");
const tri_proc = @import("tri_proc");
const stdout = std.Io.File.stdout();
const stderr = std.Io.File.stderr();

// Module definitions
const Module = struct {
    name: []const u8,
    top: []const u8,
};

const MODULES = [_]Module{
    .{ .name = "gf16_add.v", .top = "gf16_add" },
    .{ .name = "gf16_mul.v", .top = "gf16_mul" },
    .{ .name = "gf16_alu.v", .top = "gf16_alu" },
    .{ .name = "tf3_add.v", .top = "tf3_add" },
    .{ .name = "tf3_dot.v", .top = "tf3_dot" },
    .{ .name = "sacred_alu.v", .top = "sacred_alu" },
};

const SYNTH_DIR = "build";

pub fn main() !u8 {
    const io = tri_io.get();
    const allocator = std.heap.raw_c_allocator;

    const args = try std.process.argsAlloc(allocator);
    defer allocator.free(args);

    if (args.len < 2) {
        printUsage(allocator);
        return 0;
    }

    const command = args[1];
    const modules_to_synth = if (args.len > 2) args[2..] else &[_][]u8{};

    if (std.mem.eql(u8, command, "s")) {
        if (modules_to_synth.len == 0) {
            try synthesizeAll(allocator);
        } else {
            for (modules_to_synth) |name| {
                for (MODULES) |mod| {
                    if (std.mem.eql(u8, name, mod.name)) {
                        try synthesizeModule(allocator, mod);
                    }
                }
            }
        }
    } else if (std.mem.eql(u8, command, "synth")) {
        if (modules_to_synth.len != 1) {
            try stderr.writeStreamingAll(io, "Error: synth requires exactly one module\n");
            return 1;
        }
        for (modules_to_synth) |name| {
            for (MODULES) |mod| {
                if (std.mem.eql(u8, name, mod.name)) {
                    try synthesizeModule(allocator, mod);
                    return 0;
                }
            }
        }
        try stderr.writeStreamingAll(io, "Error: Unknown module\n");
        return 1;
    } else if (std.mem.eql(u8, command, "bench")) {
        try stdout.writeStreamingAll(io, "\n=== Sacred ALU Benchmarks ===\n");
        try stdout.writeStreamingAll(io, "Run: iverilog tb/tb_{module}.v + build/{module}.json\n");
        try stdout.writeStreamingAll(io, "\nNote: Requires iverilog installed\n");
    } else {
        printUsage(allocator);
        return 0;
    }

    return 0;
}

fn synthesizeAll(allocator: std.mem.Allocator) !void {
    const io = tri_io.get();
    try stdout.writeStreamingAll(io, "\n=== Sacred ALU Synthesis ===\n");
    for (MODULES) |mod| {
        try synthesizeModule(allocator, mod);
    }
}

fn synthesizeModule(allocator: std.mem.Allocator, mod: Module) !void {
    const io = tri_io.get();
    const msg = try std.fmt.allocPrint(allocator, "  {s}\n", .{mod.name});
    defer allocator.free(msg);
    try stdout.writeStreamingAll(io, msg);

    const yosys_script = try std.fmt.allocPrint(allocator, "read_verilog fpga/openxc7-synth/{s}; synth_xc7 -top {s}; json -o {s}/{s}.json", .{ mod.name, mod.top, SYNTH_DIR, mod.name });
    defer allocator.free(yosys_script);

    const yosys_argv = &[_][]const u8{
        "yosys", "-p", yosys_script,
    };

    const result = tri_proc.run(.{
        .allocator = allocator,
        .argv = yosys_argv,
    }) catch |err| {
        const err_msg = try std.fmt.allocPrint(allocator, "Error running yosys: {any}\n", .{err});
        defer allocator.free(err_msg);
        try stderr.writeStreamingAll(io, err_msg);
        return;
    };

    if (result.term.exited == 0) {
        try stdout.writeStreamingAll(io, "    \x1b[32mOK\x1b[0m\n");
    } else {
        const fail_msg = try std.fmt.allocPrint(allocator, "    \x1b[31mFAILED (code {d})\x1b[0m\n", .{result.term.exited});
        defer allocator.free(fail_msg);
        try stdout.writeStreamingAll(io, fail_msg);
    }
}

fn printUsage(allocator: std.mem.Allocator) void {
    const io = tri_io.get();
    stdout.writeStreamingAll(io, "Usage: tri sacred <command> [module...]\n") catch {};
    stdout.writeStreamingAll(io, "\nCommands:\n") catch {};
    stdout.writeStreamingAll(io, "  s           Synthesize all Sacred ALU modules\n") catch {};
    stdout.writeStreamingAll(io, "  synth <mod> Synthesize specific module\n") catch {};
    stdout.writeStreamingAll(io, "  bench       Run benchmark (requires iverilog)\n") catch {};
    stdout.writeStreamingAll(io, "\nModules:\n") catch {};
    for (MODULES) |mod| {
        const mod_msg = std.fmt.allocPrint(allocator, "  {s}\n", .{mod.name}) catch continue;
        defer allocator.free(mod_msg);
        stdout.writeStreamingAll(io, mod_msg) catch {};
    }
}
