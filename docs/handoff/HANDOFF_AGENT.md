# HANDOFF — Trinity FPGA Matrix (2026-07-06, marathon session)

> **For the agent in a new window.** Read CAREFULLY before doing anything.
> All numbers below — verified live via gh API + UART on real AX7203 hardware.
> Repo: `gHashTag/trinity-fpga` (main), `gHashTag/t27` (master), `gHashTag/trinity-papers-ru` (main).

---

## 0. HARDWARE CONSTANTS (DO NOT CONFUSE)

| Parameter | Value |
|---|---|
| Board | **ALINX AX7203** · XC7A200T-2FBG484I |
| Part | `xc7a200tfbg484-2` |
| **IDCODE** | **`0x13636093`** (NOT `0x0362D093`!) |
| JTAG cable | AL321 (FT2232H, vid 0x0403 pid 0x6014) |
| OpenOCD cfg | `fpga/openxc7-synth/ax7203_al321.cfg` |
| UART | CP2102N `/dev/cu.usbserial-120` · **baud 160000** |
| Clock | 200 MHz LVDS R4(+)/T4(−) → IBUFDS |
| openocd | `sudo /opt/homebrew/bin/openocd` (NOPASSWD for openocd) |
| iverilog | `/opt/homebrew/bin/iverilog` (v13.0) |
| STARTUPE2_mock | `fpga/openxc7-synth/STARTUPE2_mock.v` (for iverilog sim) |

---

## 1. FINAL NUMBERS (verified, terminal where marked)

### SW-axis (t27 master `6c704801`)
- **bitexact: 75** / selfconsistent: **0** / structural: **8** = **83**
- Horizon-A **TERMINAL** — 8 structural have no decode law (impossible).
- INDEX: `gHashTag/t27/conformance/vectors/INDEX_all_formats.json`

### HW Tier-E (#137 comments on issue #199)
- **decode-HW unique: 47** (41 original + gf16/4/6/8/20/12-decode)
- **compute-HW unique: 10 GF** (gf4/6/8/10/12/14/16/20/24/32 × ADD+MUL+SUB = 30 cells)
- **(cell,op) total: 77**
- **union (≥1 axis): 49 unique formats**
- **both axes (3/3 HW): 8** — gf4, gf6, gf8, gf10, gf12, gf14, gf16, gf20

### Catalog
- **= 83** (NOT 84; erratum closed, root cause E8M0 = Microscaling component)

### Routing-blocked (horizon B)
- **takum32, takum64** — nextpnr routing FAILURE (8 seeds, all fail). CI runs 28675516786/794.
- **gf24-decode, gf32-decode** — nextpnr FAILURE even without `-flatten`. CI runs 28773511637/467.
- **gf12-decode** — FIXED: `-flatten` removal → CI SUCCESS → UART 4096/4096 → Tier-E proven.
- **Root cause `-flatten`:** yosys `synth_xilinx -flatten` causes routing failure for some netlists. Fix: remove `-flatten`. Works for gf12; does NOT work for gf24/32 (deeper).

---

## 2. UNCOMMITTED WORK ON DISK (NOT COMMITTED)

### int64-decode RTL — WRITTEN, NOT COMMITTED

4 files on disk in `~/trinity-fpga/`, ready to commit:

```
fpga/openxc7-synth/int64_decode.v                    # int64→FP32 decoder
fpga/openxc7-synth/corona_decode_int64_ax7203.v      # corona wrapper (8-byte frame)
.github/workflows/ax7203-corona-decode-int64.yml      # CI workflow (no -flatten!)
conformance/int64_decode_conformance_ax7203.py        # UART golden
```

**Commands to execute:**
```bash
cd ~/trinity-fpga

# 1. Compile check
iverilog -g2012 fpga/openxc7-synth/int64_decode.v
# rc=0 = OK

# 2. iverilog sim (optional, with STARTUPE2_mock)
iverilog -g2012 -o /tmp/int64_wrap -s corona_decode_int64_ax7203 \
  fpga/openxc7-synth/corona_decode_int64_ax7203.v \
  fpga/openxc7-synth/int64_decode.v \
  fpga/openxc7-synth/STARTUPE2_mock.v

# 3. Commit + push (triggers CI synth)
git add fpga/openxc7-synth/int64_decode.v \
       fpga/openxc7-synth/corona_decode_int64_ax7203.v \
       .github/workflows/ax7203-corona-decode-int64.yml \
       conformance/int64_decode_conformance_ax7203.py
git commit -m "feat(fpga): int64 decode → FP32 (NEW cell, union 47→48)"
git push origin main

# 4. Wait for CI (~1-2h). Check:
gh run list --repo gHashTag/trinity-fpga --workflow "AX7203 Corona Decode INT64" --limit 1 --json status,conclusion

# 5. When CI GREEN — download bitstream + flash + UART:
RUN_ID=$(gh run list --repo gHashTag/trinity-fpga --workflow "AX7203 Corona Decode INT64" --limit 1 --json databaseId --jq '.[0].databaseId')
gh run download $RUN_ID -n corona-decode-int64-bitstream -D /tmp/int64dec
BIT=/tmp/int64dec/corona_decode_ax7203.bit
SHA=$(shasum -a 256 "$BIT" | cut -d' ' -f1); echo "SHA=$SHA"

# Flash
sudo /opt/homebrew/bin/openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" -c "pld load 0 $BIT" -c "runtest 200000" -c "shutdown"
# Verify IDCODE 0x13636093 in the output!

# UART verify
python3 conformance/int64_decode_conformance_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
# Expected: HW RESULT: ~2010/2010 bit-exact (fails=0)

# 6. Tier-E proof on #199
gh issue comment 199 --repo gHashTag/trinity-fpga --body "### Tier-E proof: \`int64\` DECODE (signed int64 → FP32, NEW cell)

**decode-HW 47→48. union 49→50.** NEW decode cell — int64 had no RTL before.

- **CI run:** <RUN_URL>
- **Bitstream SHA256:** \`$SHA\`
- **UART @160000:** \`HW RESULT: N/N bit-exact (fails=0)\`
- **IDCODE:** \`0x13636093\` (XC7A200T rev 1)"
```

---

## 3. NEXT FORMATS FOR RTL (simple decode → FP32, ~200-400 LUT, route fine)

After int64, the same 4 files (decoder + wrapper + CI + conformance) for each:

| Format | Complexity | LUT est. | Description |
|---|---|---|---|
| **int64** | trivial | ~200 | signed int → FP32 (ON DISK, not committed) |
| **int128** | easy | ~350 | 128-bit signed int → FP32 (wider frame = 16 bytes) |
| **posit64** | medium | ~400 | posit64 → FP32 (variable-length regime; es=4) |
| **vax_h** | easy | ~150 | VAX H_floating (128-bit) → FP32 |
| **x87_fp80** | medium | ~300 | 80-bit x87 extended → FP32 |
| **lns32** | medium | ~300 | LNS-32 → FP32 (log→linear convert) |

Pattern for each:
1. Decoder `.v` (format-specific → FP32)
2. Corona wrapper (copy from int64/gf16, change the decoder instance + frame width)
3. CI workflow (copy the template, `no -flatten`)
4. Conformance script (Python golden via struct.pack)

---

## 4. t27 PR QUEUE (24 open)

| Category | Count | What to do |
|---|---|---|
| Wave-loop 4xx (420-459) | 21 | MERGEABLE BEHIND → need `Refs #N` in body + NOW.md → CI will restart |
| CONFLICTING (425-434) | 11 | Conflicts with master → rebase manually |
| BLOCKED (454-459) | 4 | CI checks pending |
| #1225 (metrics) | 1 | standalone, MERGEABLE BEHIND |
| #1141 (OpenSSF) | 1 | standalone, MERGEABLE BEHIND |
| #1128 (gen artifacts) | 1 | CONFLICTING |

**t27 gates (ALL required):** L1 TRACEABILITY (`Closes #N` or `Refs #N` in the PR body) + check-linked-issue + check-now-freshness (`docs/NOW.md` updated) + integrity-gate.

**Strategy:** for MERGEABLE BEHIND → add `Refs #N` to body + edit NOW.md → merge. For CONFLICTING → rebase (may require manual resolution).

---

## 5. trinity-fpga PR QUEUE (4 open)

| PR | Title | What to do |
|---|---|---|
| #39 | L-DPC1 GF16 dot4 (legacy XC7A100T) | merge (no required checks) |
| #216 | formal reachability gf16 Inf/NaN | review → merge |
| #218 | formal reachability MUL gf16 | review → merge |
| #92 | CITATION.cff doi | **ALREADY MERGED** (7d29e6a78) |

---

## 6. AUTO TIER-E COUNTER

```bash
python3 scripts/tier_e_counter.py         # human-readable
python3 scripts/tier_e_counter.py --json   # JSON output
python3 scripts/tier_e_counter.py --verbose # per-format list
```

Parses #199 comments, validates 4/4 (SHA+UART+IDCODE+CI), counts decode/compute/union/both-axes.

---

## 7. HONESTY RULES (BINDING — must NOT be violated)

1. **Catalog = 83** (NOT 84; erratum E8M0).
2. **encoding ≠ compute ≠ FPGA** — three DIFFERENT axes, do not mix.
3. **Tier-E = only a 4/4 chain:** CI GREEN URL + SHA256 + UART `N/N fails=0` + IDCODE `0x13636093`. sim ≠ HW.
4. **No "first/best/only".** Positioning: "architecturally different + honestly auditable".
5. **Routing-blocked = horizon B**, do not move the count retroactively.
6. **`-flatten` in yosys** = routing FAILURE for some netlists. Use `synth_xilinx -abc9 -nocarry` (WITHOUT `-flatten`).
7. **Sandbox (Perplexity) ≠ bash (opencode)** — bash may work when the sandbox is dead, and vice versa.

---

## 8. KEY FILES

```
fpga/openxc7-synth/gf_decode_param.v          # parametric decode (gf4..gf32)
fpga/openxc7-synth/corona_decode_*_ax7203.v   # corona wrappers (all formats)
fpga/openxc7-synth/ax7203_al321.cfg           # openocd config
fpga/openxc7-synth/STARTUPE2_mock.v           # mock for iverilog sim
fpga/witness/gf_decode/                        # iverilog witness (10/10 PASS)
scripts/tier_e_counter.py                      # auto-counter for #199
conformance/                                    # all UART conformance scripts
fpga/HARDWARE_REFERENCE.md                     # hardware truth
```

---

## 9. ARXIV PAPERS (trinity-papers-ru)

| Paper | arXiv | State |
|---|---|---|
| paper1-goldenfloat | 2606.05017 | §5.3 sync (decode 47, PR #8 merged) |
| paper2-catalog | 2606.09686 | v5 (75/0/8, PR #9 merged). Erratum 84→83 |
| paper3-rossiya | (not on arXiv) | §3a.4-5 (scientific sidebars, PR #5 merged) |

**Open PRs in trinity-papers-ru = 0** (main HEAD `85231dc8`).

---

*Generated 2026-07-06, marathon session. All numbers verified on GitHub. The bash platform may be unavailable — run commands manually if needed.*
