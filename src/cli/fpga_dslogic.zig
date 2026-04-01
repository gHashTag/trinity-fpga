// DSLogic U2basic Diagnostics Tool — Trinity CLI
// Logic analyzer documentation and guide for QMTech XC7A100T FPGA
// Usage: tri fpga dslogic-*

const std = @import("std");

const Command = enum {
    connect, // Show DSView connection setup
    capture, // Show capture configuration
    analyze, // Show analysis workflow
    uart, // UART loopback test guide
    jtag, // JTAG timing validation guide
    clock, // Clock tree analysis guide
    pins, // Pin mapping verification guide
    help, // Show help
};

const Preset = enum {
    full_analysis,
    uart_debug,
    uart_loopback,
    jtag_debug,
    spi_debug,
    clock_tree,
    pin_verify,
    minimal,
};

pub fn main() !void {
    const allocator = std.heap.page_allocator;
    const args = try std.process.argsAlloc(allocator);
    defer allocator.free(args);

    if (args.len < 3) {
        try printUsage();
        std.process.exit(1);
    }

    const command = std.meta.stringToEnum(Command, args[2]) orelse {
        std.debug.print("Unknown command: {s}\n\n", .{args[2]});
        try printUsage();
        std.process.exit(1);
    };

    switch (command) {
        .connect => try cmdConnect(),
        .capture => try cmdCapture(),
        .analyze => try cmdAnalyze(),
        .uart => try cmdUartTest(),
        .jtag => try cmdJtagTiming(),
        .clock => try cmdClockAnalysis(),
        .pins => try cmdPinVerify(),
        .help => try printUsage(),
    }
}

fn printUsage() !void {
    std.debug.print(
        \\DSLogic U2basic Diagnostics — Trinity FPGA
        \\
        \\Usage: tri fpga dslogic-<command> [options]
        \\
        \\Commands:
        \\  connect              Show DSView connection setup guide
        \\  capture              Show capture configuration guide
        \\  analyze              Show analysis workflow guide
        \\  uart                 UART loopback test guide
        \\  jtag                 JTAG timing validation guide
        \\  clock                Clock tree analysis guide
        \\  pins                 Pin mapping verification guide
        \\  help                 Show this help
        \\
        \\Capture Options:
        \\  --preset <name>      Use preset (full_analysis, uart_debug, jtag_debug, clock_tree)
        \\  --duration <sec>     Capture duration in seconds (default: 1)
        \\  --output <path>      Export path (default: auto-generated)
        \\
        \\Examples:
        \\  tri fpga dslogic-connect
        \\  tri fpga dslogic-capture --preset uart_debug
        \\  tri fpga dslogic-uart
        \\  tri fpga dslogic-jtag
        \\  tri fpga dslogic-clock
        \\  tri fpga dslogic-pins
        \\
        \\φ² + 1/φ² = 3 = TRINITY
        \\
        , .{});
}

// ─────────────────────────────────────────────────────────────────────────────
// Command: connect — Show DSView connection setup
// ─────────────────────────────────────────────────────────────────────────────

fn cmdConnect() !void {
    std.debug.print("DSLogic U2basic — Connection Setup Guide\n", .{});
    std.debug.print("═\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Step 1: Connect DSLogic U2basic\n", .{});
    std.debug.print("  1. Connect USB cable to MacBook\n", .{});
    std.debug.print("  2. Launch DSView (or run 'open -a DSView')\n", .{});
    std.debug.print("  3. Device should auto-detect\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Step 2: Load Trinity Presets\n", .{});
    std.debug.print("  1. In DSView: File → Open → Open Workspace/Session File\n", .{});
    std.debug.print("  2. Select: fpga/dslogic_presets.json\n", .{});
    std.debug.print("  3. Channel mapping and decoders will load automatically\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Quick Start:\n", .{});
    std.debug.print("  1. Select channels to display (CH0-CH15)\n", .{});
    std.debug.print("  2. Set sample rate to 400 MS/s\n", .{});
    std.debug.print("  3. Set trigger condition\n", .{});
    std.debug.print("  4. Press 'Single' or 'Run' to capture\n", .{});
}

// ─────────────────────────────────────────────────────────────────────────────
// Command: capture — Show capture configuration
// ─────────────────────────────────────────────────────────────────────────────

fn cmdCapture() !void {
    std.debug.print("DSLogic Capture — Configuration Guide\n", .{});
    std.debug.print("═\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Available Presets:\n", .{});
    std.debug.print("  • full_analysis  - All 16 channels for comprehensive analysis\n", .{});
    std.debug.print("  • uart_debug    - UART TX/RX with 50MHz clock\n", .{});
    std.debug.print("  • uart_loopback - UART loopback test\n", .{});
    std.debug.print("  • jtag_debug    - JTAG timing validation\n", .{});
    std.debug.print("  • clock_tree    - 50MHz + MMCM clock analysis\n", .{});
    std.debug.print("  • pin_verify    - Pin mapping verification\n", .{});
    std.debug.print("  • minimal       - UART-only (fast start)\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("DSView Configuration Steps:\n", .{});
    std.debug.print("  1. Sample Rate: 400 MS/s\n", .{});
    std.debug.print("  2. Channels: Select based on preset\n", .{});
    std.debug.print("  3. Trigger: Set based on preset (see guide)\n", .{});
    std.debug.print("  4. Decoders: Enable UART/JTAG as needed\n", .{});
}

// ─────────────────────────────────────────────────────────────────────────────
// Command: analyze — Show analysis workflow
// ─────────────────────────────────────────────────────────────────────────────

fn cmdAnalyze() !void {
    std.debug.print("DSLogic Analysis — Signal Data Processing\n", .{});
    std.debug.print("═\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Analysis Workflow:\n", .{});
    std.debug.print("  1. Capture signals in DSView (see 'capture' command)\n", .{});
    std.debug.print("  2. Export data: File → Export → CSV/JSON/VCD\n", .{});
    std.debug.print("  3. Analyze in DSView:\n", .{});
    std.debug.print("     - Add protocol decoders (UART, JTAG, etc.)\n", .{});
    std.debug.print("     - Measure timings (pulse width, frequency, delays)\n", .{});
    std.debug.print("     - Search patterns (specific byte sequences)\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Export Formats:\n", .{});
    std.debug.print("  • CSV   - For Excel/Python analysis\n", .{});
    std.debug.print("  • JSON  - For automation scripts\n", .{});
    std.debug.print("  • VCD   - For GTKWave visualization\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Note: Use 'tri fpga dslogic-*' commands for specific workflows\n", .{});
}

// ─────────────────────────────────────────────────────────────────────────────
// Command: uart — UART loopback test workflow
// ─────────────────────────────────────────────────────────────────────────────

fn cmdUartTest() !void {
    std.debug.print("DSLogic UART Loopback Test\n", .{});
    std.debug.print("═\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Hardware Setup:\n", .{});
    std.debug.print("  GND  → J2 Pin 1  (⬛ black, connect FIRST!)\n", .{});
    std.debug.print("  CH0  → J2 Pin 5  (🟡 yellow = FPGA TX)\n", .{});
    std.debug.print("  CH1  → J2 Pin 6  (🟢 green = FPGA RX)\n", .{});
    std.debug.print("  CH2  → M22       (🔵 blue = 50 MHz Clock)\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("DSView Configuration:\n", .{});
    std.debug.print("  • Sample Rate: 400 MS/s\n", .{});
    std.debug.print("  • Channels: 0, 1, 2, 15 (GND)\n", .{});
    std.debug.print("  • Trigger: Falling edge on CH0 (UART TX start bit)\n", .{});
    std.debug.print("  • Decoder: UART @ 115200 baud, 8N1\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Test Procedure:\n", .{});
    std.debug.print("  1. Start capture in DSView\n", .{});
    std.debug.print("  2. Send UART command (e.g., via CoolTerm: 0x03 PING)\n", .{});
    std.debug.print("  3. Stop capture\n", .{});
    std.debug.print("  4. Analyze results:\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Expected Results:\n", .{});
    std.debug.print("  CH0 (TX): 0x03 ... (PING bytes)\n", .{});
    std.debug.print("  CH1 (RX): 0x83 ... (PONG response)\n", .{});
    std.debug.print("  Bit width: ~8.68 μs @ 115200 baud\n", .{});
    std.debug.print("  TX→RX delay: < 100 ns\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Troubleshooting:\n", .{});
    std.debug.print("  ❌ No signal: Check GND connection and probe wiring\n", .{});
    std.debug.print("  ❌ Wrong data: Verify baud rate matches (115200)\n", .{});
    std.debug.print("  ❌ No RX: FPGA may not be running - check bitstream\n", .{});
}

// ─────────────────────────────────────────────────────────────────────────────
// Command: jtag — JTAG timing validation guide
// ─────────────────────────────────────────────────────────────────────────────

fn cmdJtagTiming() !void {
    std.debug.print("DSLogic JTAG Timing Validation\n", .{});
    std.debug.print("═\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("⚠️  CRITICAL: Disconnect Xilinx JTAG cable before connecting DSLogic!\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Hardware Setup:\n", .{});
    std.debug.print("  GND   → JTAG Pin 2 or J2 Pin 1 (⬛ black)\n", .{});
    std.debug.print("  CH9   → JTAG Pin 3 (TCK) 🟤 brown\n", .{});
    std.debug.print("  CH11  → JTAG Pin 4 (TDO) 🟗 lime\n", .{});
    std.debug.print("  CH10  → JTAG Pin 5 (TDI) 🟡 beige\n", .{});
    std.debug.print("  CH12  → JTAG Pin 6 (TMS) 🔷 turquoise\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("DSView Configuration:\n", .{});
    std.debug.print("  • Sample Rate: 400 MS/s\n", .{});
    std.debug.print("  • Channels: 9, 10, 11, 12, 15\n", .{});
    std.debug.print("  • Trigger: Rising edge on CH9 (TCK)\n", .{});
    std.debug.print("  • Decoder: JTAG\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Expected JTAG Timing (Xilinx spec):\n", .{});
    std.debug.print("  • TCK frequency: Variable (auto-detected)\n", .{});
    std.debug.print("  • Setup time (TDO→TCK): < 10 ns\n", .{});
    std.debug.print("  • Hold time (TCK→TDI): < 10 ns\n", .{});
    std.debug.print("  • TMS valid before TCK: > 10 ns\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Analysis Checklist:\n", .{});
    std.debug.print("  ✅ TCK signal is clean (no glitches)\n", .{});
    std.debug.print("  ✅ TDO changes within setup time\n", .{});
    std.debug.print("  ✅ TDI stable during hold time\n", .{});
    std.debug.print("  ✅ TMS state transitions are correct\n", .{});
}

// ─────────────────────────────────────────────────────────────────────────────
// Command: clock — Clock tree analysis guide
// ─────────────────────────────────────────────────────────────────────────────

fn cmdClockAnalysis() !void {
    std.debug.print("DSLogic Clock Tree Analysis\n", .{});
    std.debug.print("═\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Hardware Setup:\n", .{});
    std.debug.print("  GND  → J2 Pin 1 (⬛ black)\n", .{});
    std.debug.print("  CH2  → M22 (🔵 blue = 50 MHz oscillator)\n", .{});
    std.debug.print("  CH3  → U22 (🟣 purple = MMCM output)\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("DSView Configuration:\n", .{});
    std.debug.print("  • Sample Rate: 400 MS/s\n", .{});
    std.debug.print("  • Channels: 2, 3, 15\n", .{});
    std.debug.print("  • Trigger: Pulse on CH2 (min width 18ns)\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Expected Results:\n", .{});
    std.debug.print("  CH2 (50 MHz):\n", .{});
    std.debug.print("    • Frequency: 50.0 MHz ± 0.1%\n", .{});
    std.debug.print("    • Period: 20.0 ns\n", .{});
    std.debug.print("    • Duty cycle: ~50%\n", .{});
    std.debug.print("\n", .{});
    std.debug.print("  CH3 (MMCM - HSLM config):\n", .{});
    std.debug.print("    • Frequency: 81.25 MHz\n", .{});
    std.debug.print("    • Period: 12.31 ns\n", .{});
    std.debug.print("    • Lock status: Stable (no glitches)\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Analysis Checklist:\n", .{});
    std.debug.print("  ✅ CH2 frequency within tolerance (50.0 MHz ± 0.1%)\n", .{});
    std.debug.print("  ✅ CH3 frequency is 81.25 MHz (1.625x CH2)\n", .{});
    std.debug.print("  ✅ Both signals are stable (no frequency drift)\n", .{});
    std.debug.print("  ✅ Jitter < 100 ps RMS\n", .{});
    std.debug.print("  ✅ Phase relationship is consistent\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("If CH3 is unstable:\n", .{});
    std.debug.print("  → MMCM may not be locked - check bitstream\n", .{});
    std.debug.print("  → Power supply issue - measure 3.3V rail\n", .{});
    std.debug.print("  → Wrong MMCM configuration - check constraints\n", .{});
}

// ─────────────────────────────────────────────────────────────────────────────
// Command: pins — Pin mapping verification guide
// ─────────────────────────────────────────────────────────────────────────────

fn cmdPinVerify() !void {
    std.debug.print("DSLogic Pin Mapping Verification\n", .{});
    std.debug.print("═\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("This test verifies the J2 pin mapping:\n", .{});
    std.debug.print("  Documentation says: J2 pin 5/6 → D26/E26\n", .{});
    std.debug.print("  Constraint file uses: K20/L20\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Hardware Setup:\n", .{});
    std.debug.print("  GND  → J2 Pin 1 (⬛ black)\n", .{});
    std.debug.print("  CH0  → J2 Pin 5 (🟡 yellow = K20 per XDC)\n", .{});
    std.debug.print("  CH13 → D26 (🔵 dark blue = alt mapping)\n", .{});
    std.debug.print("  CH1  → J2 Pin 6 (🟢 green = L20 per XDC)\n", .{});
    std.debug.print("  CH14 → E26 (🟢 dark green = alt mapping)\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Test Procedure:\n", .{});
    std.debug.print("  1. Flash uart_echo_top.bit to FPGA\n", .{});
    std.debug.print("  2. Start DSView capture (all 4 channels)\n", .{});
    std.debug.print("  3. Send UART data (e.g., 0x55 via CoolTerm)\n", .{});
    std.debug.print("  4. Observe which channel captures the data\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("Interpretation:\n", .{});
    std.debug.print("  ┌─────────────┬──────────────┬─────────────────┐\n", .{});
    std.debug.print("  │ CH0 captures │ CH13 captures │ Conclusion      │\n", .{});
    std.debug.print("  ├─────────────┼──────────────┼─────────────────┤\n", .{});
    std.debug.print("  │ Yes         │ No           │ K20 is correct  │\n", .{});
    std.debug.print("  │ No          │ Yes          │ D26 is correct  │\n", .{});
    std.debug.print("  │ Both        │ Both         │ Both connected  │\n", .{});
    std.debug.print("  │ Neither     │ Neither      │ UART TX broken  │\n", .{});
    std.debug.print("  └─────────────┴──────────────┴─────────────────┘\n", .{});
    std.debug.print("\n", .{});

    std.debug.print("If D26/E26 is correct:\n", .{});
    std.debug.print("  → Update fpga/constraints/uart_bridge_j2.xdc:\n", .{});
    std.debug.print("    set_property -dict {{PACKAGE_PIN D26 ...}} [get_ports uart_tx]\n", .{});
    std.debug.print("    set_property -dict {{PACKAGE_PIN E26 ...}} [get_ports uart_rx]\n", .{});
    std.debug.print("  → Rebuild: tri fpga build-uart\n", .{});
    std.debug.print("  → Update this finding to .trinity/fpga/experience.json\n", .{});
}
