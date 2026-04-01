//! FPGA Flash Tool — Mac JTAG procedure for Xilinx DLC10 + XC7A100T
//! Replaces: step1_fxload.sh, step2_verify_pid.sh, step3_fxload_again.sh, step4_flash.sh
//!
//! Usage:
//!   fpga-flash fxload       # First firmware load
//!   fpga-flash verify-pid   # Check DLC10 PID
//!   fpga-flash flash        # Flash bitstream
//!   fpga-flash uart-test    # Test UART bridge
//!   fpga-flash full         # Complete procedure

const std = @import("std");
const fs = std.fs;
const process = std.process;
const mem = std.mem;

const FXLOAD_PATH = "/Users/playra/trinity-w1/fpga/tools/fxload";
const FIRMWARE_PATH = "/Users/playra/trinity-w1/fpga/tools/xusb_xp2.hex";
const XC3SPROG_PATH = "/Users/playra/trinity-w1/fpga/tools/xc3sprog";
const BITSTREAM_PATH = "/Users/playra/trinity-w1/fpga/openxc7-synth/uart_bridge_fixed.bit";
const UART_TEST_PATH = "/Users/playra/trinity-w1/fpga/uart_test.py";

pub fn main() !void {
    const gpa = std.heap.page_allocator;

    const args = try std.process.argsAlloc(gpa);
    defer std.process.argsFree(gpa, args);

    if (args.len < 2) {
        printUsage();
        return error.InvalidArgs;
    }

    const command = args[1];

    if (mem.eql(u8, command, "fxload")) {
        try runFxload();
    } else if (mem.eql(u8, command, "verify-pid")) {
        try verifyPid();
    } else if (mem.eql(u8, command, "flash")) {
        try flashBitstream();
    } else if (mem.eql(u8, command, "uart-test")) {
        try runUartTest();
    } else if (mem.eql(u8, command, "full")) {
        try runFullProcedure();
    } else {
        std.debug.print("Unknown command: {s}\n\n", .{command});
        printUsage();
        return error.InvalidArgs;
    }
}

fn printUsage() void {
    std.debug.print(
        \\FPGA Flash Tool — Mac JTAG for Xilinx DLC10 + XC7A100T
        \\
        \\Usage:
        \\  fpga-flash fxload       # Load FX2 firmware (first time)
        \\  fpga-flash verify-pid   # Check DLC10 PID (0x0008 = JTAG mode)
        \\  fpga-flash flash        # Flash uart_bridge_fixed.bit
        \\  fpga-flash uart-test    # Test UART bridge
        \\  fpga-flash full         # Complete procedure
        \\
        \\Mac JTAG Procedure:
        \\  1. fpga-flash fxload      # Load firmware
        \\  2. PHYSICAL REPLUG DLC10  # Unplug & replug USB
        \\  3. fpga-flash fxload      # Load again (CRITICAL!)
        \\  4. fpga-flash verify-pid  # Check PID = 0x0008
        \\  5. fpga-flash flash       # Flash bitstream
        \\  6. fpga-flash uart-test   # Test UART
        \\
    , .{});
}

fn runFxload() !void {
    std.debug.print("\x1b[34m═════════════════════════════════════════\x1b[0m\n", .{});
    std.debug.print("\x1b[34mSTEP: Load FX2 Firmware\x1b[0m\n", .{});
    std.debug.print("\x1b[34m═════════════════════════════════════════\x1b[0m\n\n", .{});

    std.debug.print("DLC10 PID: 0x0013 (bootloader mode)\n", .{});
    std.debug.print("Loading firmware: {s} ({d} bytes)\n\n", .{
        FIRMWARE_PATH,
        try getFileSize(FIRMWARE_PATH),
    });

    const result = try execCommand(&.{
        "sudo",
        FXLOAD_PATH,
        "-v",
        "-t",
        "fx2",
        "-d",
        "03fd:0013",
        "-i",
        FIRMWARE_PATH,
    });

    std.debug.print("{s}\n", .{result});

    std.debug.print("\n\x1b[32m✅ Firmware loaded!\x1b[0m\n", .{});
    std.debug.print("\n\x1b[33m🔌 PHYSICAL REPLUG REQUIRED!\x1b[0m\n", .{});
    std.debug.print("   1. UNPLUG DLC10 USB cable\n", .{});
    std.debug.print("   2. Wait 3 seconds\n", .{});
    std.debug.print("   3. REPLUG DLC10 USB cable\n", .{});
    std.debug.print("   4. Run: fpga-flash fxload\n\n", .{});
}

fn verifyPid() !void {
    std.debug.print("\x1b[34m═════════════════════════════════════════\x1b[0m\n", .{});
    std.debug.print("\x1b[34mSTEP: Verify DLC10 PID\x1b[0m\n", .{});
    std.debug.print("\x1b[34m═════════════════════════════════════════\x1b[0m\n\n", .{});

    const result = try execCommand(&.{ "system_profiler", "SPUSBDataType" });
    const xilinx_section = findXilinxSection(result) orelse {
        std.debug.print("❌ DLC10 NOT found!\n", .{});
        std.debug.print("   Check USB connection\n", .{});
        return error.DeviceNotFound;
    };

    const pid = findProductId(xilinx_section) orelse "unknown";
    std.debug.print("DLC10 Product ID: {s}\n\n", .{pid});

    if (mem.eql(u8, pid, "0x0008")) {
        std.debug.print("\x1b[32m✅ JTAG MODE ACTIVE (PID 0x0008)\x1b[0m\n", .{});
        std.debug.print("   Ready for flashing!\n\n", .{});
        std.debug.print("Next: fpga-flash flash\n\n", .{});
    } else if (mem.eql(u8, pid, "0x0013")) {
        std.debug.print("\x1b[33m⚠️  BOOTLOADER MODE (PID 0x0013)\x1b[0m\n", .{});
        std.debug.print("   Need to run fxload again!\n\n", .{});
        std.debug.print("Next: fpga-flash fxload\n\n", .{});
    } else {
        std.debug.print("\x1b[31m❌ UNKNOWN PID: {s}\x1b[0m\n", .{pid});
        return error.UnknownPid;
    }
}

fn flashBitstream() !void {
    std.debug.print("\x1b[34m═════════════════════════════════════════\x1b[0m\n", .{});
    std.debug.print("\x1b[34mSTEP: Flash uart_bridge_fixed.bit\x1b[0m\n", .{});
    std.debug.print("\x1b[34m═════════════════════════════════════════\x1b[0m\n\n", .{});

    const bitstream_size = try getFileSize(BITSTREAM_PATH);
    std.debug.print("Bitstream: {s} ({d} bytes)\n\n", .{ BITSTREAM_PATH, bitstream_size });

    const result = try execCommand(&.{ "sudo", XC3SPROG_PATH, "-c", "xpc", BITSTREAM_PATH });
    std.debug.print("{s}\n", .{result});

    // Check if flash was successful
    if (std.mem.indexOf(u8, result, "done") != null or
        std.mem.indexOf(u8, result, "VERIFY OK") != null)
    {
        std.debug.print("\n\x1b[32m✅ Flash successful!\x1b[0m\n\n", .{});

        // Restore FTDI driver
        std.debug.print("Restoring FTDI driver...\n", .{});
        _ = execCommand(&.{ "sudo", "kextload", "-b", "com.apple.driver.AppleUSBFTDI" }) catch {};

        // Kill screen processes
        std.debug.print("Killing screen processes...\n", .{});
        _ = execCommand(&.{ "killall", "screen" }) catch {};

        std.debug.print("\nNext: fpga-flash uart-test\n\n", .{});
    } else {
        std.debug.print("\n\x1b[31m❌ Flash may have failed\x1b[0m\n", .{});
        std.debug.print("Check output above for errors\n\n", .{});
    }
}

fn runUartTest() !void {
    std.debug.print("\x1b[34m═════════════════════════════════════════\x1b[0m\n", .{});
    std.debug.print("\x1b[34mSTEP: UART Bridge Test\x1b[0m\n", .{});
    std.debug.print("\x1b[34m═════════════════════════════════════════\x1b[0m\n\n", .{});

    std.debug.print("Sending 'aaaa\\r\\n' to /dev/cu.usbserial-2140...\n\n", .{});

    const result = try execCommand(&.{ "python3", UART_TEST_PATH });
    std.debug.print("{s}\n", .{result});

    if (std.mem.indexOf(u8, result, "UART RX: b''") != null) {
        std.debug.print("\n\x1b[33m⚠️  RX empty - no echo from FPGA\x1b[0m\n", .{});
        std.debug.print("   Possible issues:\n", .{});
        std.debug.print("   - Wrong bitstream (hslm_full_top instead of uart_bridge)\n", .{});
        std.debug.print("   - Pin mapping mismatch\n", .{});
        std.debug.print("   - UART bridge logic broken\n\n", .{});
    } else if (std.mem.indexOf(u8, result, "aaaa") != null) {
        std.debug.print("\n\x1b[32m✅ UART echo working!\x1b[0m\n\n", .{});
    }
}

fn runFullProcedure() !void {
    std.debug.print("\x1b[34m═════════════════════════════════════════\x1b[0m\n", .{});
    std.debug.print("\x1b[34mFULL JTAG PROCEDURE\x1b[0m\n", .{});
    std.debug.print("\x1b[34m═════════════════════════════════════════\x1b[0m\n\n", .{});

    std.debug.print("This will:\n", .{});
    std.debug.print("  1. Load FX2 firmware\n", .{});
    std.debug.print("  2. Wait for PHYSICAL REPLUG\n", .{});
    std.debug.print("  3. Load firmware again\n", .{});
    std.debug.print("  4. Verify PID = 0x0008\n", .{});
    std.debug.print("  5. Flash uart_bridge_fixed.bit\n", .{});
    std.debug.print("  6. Test UART\n\n", .{});

    std.debug.print("Starting full procedure...\n\n", .{});

    // Step 1: First fxload
    try runFxload();

    std.debug.print("\n\x1b[33m═══ PHYSICAL REPLUG REQUIRED NOW ═══\x1b[0m\n", .{});
    std.debug.print("Unplug DLC10, wait 3s, replug...\n\n", .{});

    // Step 2: Second fxload
    try runFxload();

    // Step 3: Verify PID
    try verifyPid();

    // Step 4: Flash
    try flashBitstream();

    // Step 5: Test UART
    try runUartTest();
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

fn execCommand(args: []const []const u8) ![]u8 {
    const gpa = std.heap.page_allocator;
    const result = try process.Child.run(.{
        .allocator = gpa,
        .argv = args,
    });

    if (result.term.Exited != 0 and result.term.Exited != 1) {
        // Exit code 1 might be from grep/find not finding anything
        // Other exit codes are actual errors
        return error.CommandFailed;
    }

    return result.stdout;
}

fn getFileSize(path: []const u8) !u64 {
    const file = try std.fs.openFileAbsolute(path, .{});
    defer file.close();
    return try file.getEndPos();
}

fn findXilinxSection(output: []const u8) ?[]const u8 {
    if (std.mem.indexOf(u8, output, "Xilinx Inc.")) |pos| {
        const start = if (std.mem.lastIndexOfScalar(u8, output[0..pos], '\n')) |nl_pos| nl_pos + 1 else 0;
        const end = if (std.mem.indexOf(u8, output[pos..], "\n\n")) |nl_pos| pos + nl_pos else output.len;
        return output[start..end];
    }
    return null;
}

fn findProductId(section: []const u8) ?[]const u8 {
    if (std.mem.indexOf(u8, section, "Product ID:")) |pos| {
        const value_start = pos + 12; // "Product ID:".len
        const value_end = if (std.mem.indexOf(u8, section[value_start..], "\n")) |nl| value_start + nl else section.len;
        const value = std.mem.trim(u8, section[value_start..value_end], &std.ascii.whitespace);
        return value;
    }
    return null;
}
