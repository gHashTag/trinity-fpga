#!/bin/bash
# Record Terminalizer session and render GIF
# ══════════════════════════════════════════════════════════════════════════════════════
# φ² + 1/φ² = 3 = TRINITY
# ══════════════════════════════════════════════════════════════════════════════════

SESSION_DIR="/private/tmp/trinity_demo"
GIF_FILE="$SESSION_DIR/demo.txt"

# Ensure clean session directory
rm -rf "$SESSION_DIR" 2>/dev/null
mkdir -p "$SESSION_DIR"

# Start recording
cd "$SESSION_DIR"
npx terminalizer record "$SESSION_DIR/demo" --title "Trinity Demo" --quiet

# Wait a moment
sleep 2

# Type commands
sleep 2
npx terminalizer type "clear"
sleep 1
npx terminalizer type "tri math sacred"
sleep 1
npx terminalizer type ""
sleep 6

# Stop recording
sleep 1
npx terminalizer stop

# Render GIF
npx terminalizer render "$SESSION_DIR/demo.yml" --output "$SESSION_DIR/demo.gif"

# Done
echo "✅ Demo recorded: $SESSION_DIR/demo.txt"
echo "✅ GIF rendered:   $SESSION_DIR/demo.gif"
echo ""
ls -lh "$SESSION_DIR/demo.gif"

exit 0
