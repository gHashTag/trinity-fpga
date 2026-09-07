#!/bin/bash
# NOTE (2026-08-05): per the no-shell-scripts rule (CLAUDE.md),
# fpga/**/*.sh is slated to migrate to `tri` subcommands / Zig.
# Do not extend this script; disposition tracked in trinity-fpga#425.
# A Zig replacement already exists: prefer `fpga-flash` (src/cli/fpga_flash.zig,
# subcommands fxload|verify-pid|flash|uart-test|full).
# Flash quantum bridge bitstream with auto-initialization

# Resolve tool paths relative to this script (was hardcoded to
# /Users/playom/trinity-fpga). Override the bitstream via $1 or FPGA_DIR.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FPGA_DIR="${FPGA_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
BITSTREAM="${1:-$FPGA_DIR/openxc7-synth/quantum_bridge_violation.bit}"
FXLOAD="$SCRIPT_DIR/fxload"
FIRMWARE="$SCRIPT_DIR/xusb_xp2.hex"
JTAG_PROG="$SCRIPT_DIR/jtag_program"

echo "🔌 Initializing JTAG cable..."
sudo "$FXLOAD" -t fx2 -d 03fd:0013 -i "$FIRMWARE" 2>/dev/null

echo "⚡ Flashing: $BITSTREAM"
sudo "$JTAG_PROG" "$BITSTREAM"

echo "✅ Done!"
