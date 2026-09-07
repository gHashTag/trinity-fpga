#!/bin/bash
# NOTE (2026-08-05): per the no-shell-scripts rule (CLAUDE.md),
# fpga/**/*.sh is slated to migrate to `tri` subcommands / Zig.
# Do not extend this script; disposition tracked in trinity-fpga#425.
# A Zig replacement already exists: prefer `fpga-flash` (src/cli/fpga_flash.zig,
# subcommands fxload|verify-pid|flash|uart-test|full).
# ═════════════════════════════════════════════════════════════════════════
# VSA FPGA — FULLY AUTONOMOUS FLASH + TEST
# ═════════════════════════════════════════════════════════════════════════

set -e

# Resolve paths relative to this script so the flasher is portable
# (was hardcoded to /Users/playom/trinity-fpga). Override with FPGA_DIR if needed.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FPGA_DIR="${FPGA_DIR:-$SCRIPT_DIR}"
BITFILE="$FPGA_DIR/openxc7-synth/vsa_uart_top.bit"
TOOLS="$FPGA_DIR/tools"
TEST_BIN="$FPGA_DIR/openxc7-synth/vsa_fpga_test"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     VSA FPGA — AUTONOMOUS FLASH + TEST                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Load firmware
echo "[1/4] Loading firmware to cable..."
"$TOOLS/fxload" -v -t fx2 -d 03fd:0013 -i "$TOOLS/xusb_xp2.hex"
echo "  Firmware loaded! PID should be 0x0008 now"
echo ""

# Step 2: Tell user to reconnect
echo "════════════════════════════════════════════════════════════════"
echo "🔌 RECONNECT USB CABLE NOW! (unplug & plug back in)"
echo "════════════════════════════════════════════════════════════════"
echo ""
read -p "Press ENTER after reconnecting..."

# Step 3: Flash
echo ""
echo "[2/4] Programming FPGA..."
"$TOOLS/jtag_program" "$BITFILE"
echo "  ✓ Flash complete!"
echo ""

# Step 4: Build test if needed
if [ ! -f "$TEST_BIN" ]; then
    echo "[3/4] Building test program..."
    cd "$FPGA_DIR/openxc7-synth"
    zig build-exe vsa_fpga_test.zig -O ReleaseFast
    echo "  ✓ Test program built"
fi

# Step 5: Run ping test
echo ""
echo "[4/4] Running tests..."
echo "─────────────────────────────────────────────────────────────────"

echo ""
echo "TEST: Ping..."
if "$TEST_BIN" ping 2>&1; then
    echo "  ✓ PING PASSED"
else
    echo "  ✗ PING FAILED (UART not connected?)"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✓ COMPLETE! φ² + 1/φ² = 3 = TRINITY"
echo "════════════════════════════════════════════════════════════════"
