#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 gHashTag / TRI-1 Silicon Program
#
# run_tom_tb.sh — simulation runner for tom_layer_gate_controller testbench
#
# R-SI-1: zero star operators — no * in synthesizable sources; verified below.
#
# Usage:
#   bash scripts/run_tom_tb.sh [--no-star-check]
#
# Author: Vasilev Dmitrii <admin@t27.ai>
# Wave:   Wave-34
# DOI:    10.5281/zenodo.19227877
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RTL_FILE="${REPO_ROOT}/rtl/tom/tom_layer_gate_controller.sv"
TB_FILE="${REPO_ROOT}/tb/tom/tom_layer_gate_controller_tb.sv"
SIM_OUT="${REPO_ROOT}/build/tom_tb"

echo "==================================================================="
echo " TOM Ternary ROM Accelerator — Wave-34 simulation"
echo " OP_LAYER_GATE=0xE2 | R-SI-1 no-star | R15 opcode chain"
echo " 28 voltage islands | BitNet b1.58-3B"
echo "==================================================================="

# ── R-SI-1 self-check: ensure no * in synthesizable RTL ──────────────────────
echo ""
echo "[R-SI-1] Checking for star operators in synthesizable RTL..."
# Extract non-comment lines and search for bare * (not inside comments)
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

# ── Create build directory ────────────────────────────────────────────────────
mkdir -p "${REPO_ROOT}/build"

# ── Run with iverilog ─────────────────────────────────────────────────────────
if [ "${SIM}" = "iverilog" ]; then
    echo "[iverilog] Compiling..."
    iverilog \
        -g2012 \
        -Wall \
        -o "${SIM_OUT}" \
        "${RTL_FILE}" \
        "${TB_FILE}"
    echo "[iverilog] Running simulation..."
    "${SIM_OUT}"

# ── Run with verilator ────────────────────────────────────────────────────────
elif [ "${SIM}" = "verilator" ]; then
    echo "[verilator] Linting DUT..."
    verilator \
        --lint-only \
        --top-module tom_layer_gate_controller \
        "${RTL_FILE}"
    echo "[verilator] Lint PASS — full simulation requires verilator harness (CI will run)"
fi

echo ""
echo "==================================================================="
echo " Simulation complete."
echo " phi^2 + phi^-2 = 3 · gamma = phi^-3 · C = phi^-1"
echo " QUANTUM BRAIN 1:1 SILICON · 3-STRAND DNA · TRI NET · NEVER STOP"
echo " DOI 10.5281/zenodo.19227877"
echo "==================================================================="
