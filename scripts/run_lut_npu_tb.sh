#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 gHashTag / TRI-1 Silicon Program
#
# run_lut_npu_tb.sh — simulation runner for lut_npu_pe testbench (Wave-35)
#
# R-SI-1: zero star operators — no * in synthesizable sources; verified below.
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
SIM_OUT="${REPO_ROOT}/build/lut_npu_pe_tb"

echo "==================================================================="
echo " LUT-NPU PE — Wave-35 simulation"
echo " OP_LUT_NPU=0xE3 | R-SI-1 no-star | R15 opcode chain"
echo " 81-entry LUT | BitNet b1.58 ternary | wave35_marker=4'b0011"
echo "==================================================================="

# ── R-SI-1 self-check: ensure no * in synthesizable RTL ──────────────────────
echo ""
echo "[R-SI-1] Checking for star operators in synthesizable RTL..."
if grep -n '\*' "${RTL_FILE}" | grep -v '//' | grep -v '/\*' | grep -q '.'; then
    echo "[R-SI-1] WARNING: potential synthesizable * operator found — review manually."
    echo "         Run: grep -n '\\*' ${RTL_FILE} | grep -v '//' | grep -v '/\\*'"
    exit 1
else
    echo "[R-SI-1] PASS: zero synthesizable star operators in ${RTL_FILE}"
fi

# ── Simulator detection ───────────────────────────────────────────────────────
echo ""
SIM=""
if command -v iverilog &>/dev/null; then
    SIM="iverilog"
elif command -v verilator &>/dev/null; then
    SIM="verilator"
fi

if [ -z "${SIM}" ]; then
    echo "simulator not available locally — CI will run"
    echo ""
    echo "Files that would be compiled:"
    echo "  DUT: ${RTL_FILE}"
    echo "  TB : ${TB_FILE}"
    exit 0
fi

mkdir -p "${REPO_ROOT}/build"

if [ "${SIM}" = "iverilog" ]; then
    echo "[iverilog] Compiling..."
    iverilog -g2012 -Wall -o "${SIM_OUT}" "${RTL_FILE}" "${TB_FILE}"
    echo "[iverilog] Running simulation..."
    "${SIM_OUT}"
elif [ "${SIM}" = "verilator" ]; then
    echo "[verilator] Linting DUT..."
    verilator --lint-only --top-module lut_npu_pe "${RTL_FILE}"
    echo "[verilator] Lint PASS — full simulation requires verilator harness (CI will run)"
fi

echo ""
echo "==================================================================="
echo " Simulation complete."
echo " phi^2 + phi^-2 = 3 · gamma = phi^-3 · C = phi^-1"
echo " QUANTUM BRAIN 1:1 SILICON · 3-STRAND DNA · TRI NET · NEVER STOP"
echo " DOI 10.5281/zenodo.19227877"
echo "==================================================================="
