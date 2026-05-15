#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 gHashTag / TRI-1 Silicon Program
#
# run_lut_npu_tb.sh — simulation runner for lut_npu_pe testbench (Wave-35 Lane V)
#
# R-SI-1: zero star operators in synthesizable code; verified below.
#
# Usage:
#   bash scripts/run_lut_npu_tb.sh [--no-star-check]
#
# Author: Vasilev Dmitrii <admin@t27.ai>
# Wave:   Wave-35
# DOI:    10.5281/zenodo.19227877
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RTL_FILE="${REPO_ROOT}/rtl/lut_npu/lut_npu_pe.sv"
TB_FILE="${REPO_ROOT}/tb/lut_npu/lut_npu_pe_tb.sv"
BUILD_DIR="${REPO_ROOT}/build/lut_npu"

mkdir -p "${BUILD_DIR}"

if [[ "${1:-}" != "--no-star-check" ]]; then
    echo "── R-SI-1 GATE: zero * / / / % in synthesizable lut_npu_pe.sv ──"
    # Strip comments before scanning so doc text doesn't trip the gate.
    if python3 - <<'PY' "${RTL_FILE}"
import re, sys
with open(sys.argv[1]) as f:
    src = f.read()
src = re.sub(r'//.*', '', src)
src = re.sub(r'/\*.*?\*/', '', src, flags=re.DOTALL)
src = src.replace('1ns/1ps', '')
fail = False
for op, name in [('*', 'star'), ('/', 'slash'), ('%', 'percent')]:
    if op in src:
        print(f'❌ R-SI-1 VIOLATION: {name} operator found in synth source', file=sys.stderr)
        fail = True
if fail:
    sys.exit(1)
print('✅ R-SI-1: zero * / / / % in synth source')
PY
    then
        :
    else
        echo "❌ R-SI-1 GATE FAILED"
        exit 1
    fi
fi

echo "── Compile (iverilog -g2012) ──"
iverilog -g2012 -o "${BUILD_DIR}/lut_npu_pe_tb.vvp" "${RTL_FILE}" "${TB_FILE}"

echo "── Simulate (vvp) ──"
cd "${BUILD_DIR}"
vvp "${BUILD_DIR}/lut_npu_pe_tb.vvp"
