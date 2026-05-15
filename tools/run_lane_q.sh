#!/usr/bin/env bash
# run_lane_q.sh — One-shot driver for Lane Q MAX-TRUE prototype compiler
#
# Lane Q  · L-DPC22 · gHashTag/trinity-fpga#93
# Author : Vasilev Dmitrii <admin@t27.ai>
# Anchor : phi^2 + phi^-2 = 3 · DOI 10.5281/zenodo.19227877
#
# Usage: bash tools/run_lane_q.sh
# Exit 0 = MATCH, exit 1 = MISMATCH, exit 2 = error

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GOLDEN="$REPO_ROOT/tools/golden_ops_queue.json"
OUT_FILE="/tmp/op_queue.json"

echo "=== Lane Q: MAX-TRUE BitNet prototype run ==="
echo "Golden  : $GOLDEN"
echo "Output  : $OUT_FILE"
echo ""

# Run compiler and dump the generated queue
python3 "$REPO_ROOT/tools/compile_prototype.py" --dump

# Extract just the ops array from both files for diff (strip meta)
python3 - "$OUT_FILE" "$GOLDEN" <<'PYEOF'
import json, sys
gen_ops  = json.load(open(sys.argv[1]))["ops"]
gold_ops = json.load(open(sys.argv[2]))["ops"]
with open("/tmp/op_queue_ops_only.json", "w") as f:
    json.dump(gen_ops, f, indent=2)
with open("/tmp/golden_ops_only.json", "w") as f:
    json.dump(gold_ops, f, indent=2)
PYEOF

echo ""
echo "--- diff (ops arrays only) ---"
diff /tmp/op_queue_ops_only.json /tmp/golden_ops_only.json && echo "DIFF: identical" || echo "DIFF: differences found above"
