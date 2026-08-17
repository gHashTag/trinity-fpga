# Trinity-FPGA: 83 Number Formats on Open-Source Silicon

This repository proves numerical number formats on open-source FPGA tooling. Each format in the 83-entry catalog is synthesized through `yosys` + `nextpnr` (openXC7) for the Artix-7 XC7A200T (AX7203 board), flashed to silicon, and checked bit-exact against an independent software oracle. The catalog spans IEEE floats (binary16/32/64/128), posits, takums, Galois-field floats (GF4–GF64), IBM/Cray/VAX historical formats, MX variants, and LNS — every entry measurable, reproducible, and attestable on commodity hardware without a paid EDA license.

## Status

Snapshot 2026-08-18. Counts are measured, not projected. Three rows were
re-checked against their primary sources on that date and two had gone stale;
what changed is noted in the row.

| Axis | Count | Notes |
|------|-------|-------|
| SW-bitexact | 75 / 83 | Ceiling reached; remaining 8 are structural (no independent decode law) |
| decode-HW Tier-E | 41 / 83 | UART @160000 on AX7203, IDCODE `0x13636093` (matches paper.tex; README's earlier "~47" included compute cells) |
| compute-HW Tier-E | 16 cells | GF4–GF32 × {ADD, MUL}, 0 failures on silicon (vectors vary by run) |
| GF64+ on silicon | 70.1% | 359 / 512 score; two timing paths identified, fix in progress |
| Tekum benchmark | Done | GF16 wins LUT, tekum16 wins dynamic range — see findings |
| Catalog paper | **Published** | [arXiv:2606.09686](https://arxiv.org/abs/2606.09686) v2, 83 formats. Was "Ready" -- it has been submitted and is live |
| Upstream patches to the toolchain | 25 merged | 23 in [openXC7/nextpnr-xilinx](https://github.com/openXC7/nextpnr-xilinx/pulls?q=author%3AgHashTag), 2 in openXC7/demo-projects; 1 open, 2 draft |

Tier-E = rigorous evidence: dedicated proof post, hardware IDCODE + run ID, bit-exact UART witness on silicon. See `fpga/CATALOG_MATRIX_83.md` for the live SSOT.

## Quick Start

### Clone (with submodules)

The numerical core (`external/zig-golden-float`) and `external/tt-trinity-corona`
are git submodules — a plain `git clone` leaves them empty. Fetch them too:

```bash
git clone --recursive https://github.com/gHashTag/trinity-fpga.git
# or, in an existing clone:
git submodule update --init --recursive
```

### Reproduce results (no hardware required)

```bash
# Run all 12 oracle self-tests (72 formats)
make oracle

# Cross-validate oracles (7 format families)
make repro

# Run accuracy benchmark (7 formats vs exact Fraction oracle)
make bench

# Measure GF16 LUT count (requires yosys)
make lut
# Expected: ~491 LUT (86 LUT2 + 143 LUT3 + 96 LUT4 + 78 LUT5 + 88 LUT6)
```

### Build a bitstream (requires Docker + AX7203 board)

Build a bitstream with the openXC7 Docker image, flash, and test:

```bash
# 1. Synthesize + place-and-route + bitstream (Docker, no vendor tools)
docker run --rm regymm/openxc7 bash -c '
  yosys -p "read_verilog gf_adder_param.v ${DESIGN}.v; \
            synth_xilinx -abc9 -nocarry -arch xc7; write_json ${DESIGN}.json"
  nextpnr-xilinx --chipdb /chipdb-xc7a200tfbg484-2.bin \
            --json ${DESIGN}.json --xdc ${DESIGN}.xdc --write ${DESIGN}.rpt
  fasm2frames ${DESIGN}.fasm > ${DESIGN}.frames
  xc7frames2bit --frm_file ${DESIGN}.frames --bit_file ${DESIGN}.bit
'

# 2. Flash on AX7203 (XC7A200T)
sudo openocd -f board/ax7203.cfg -c "init; pld load 0 ${DESIGN}.bit; exit"

# 3. Run bit-exact conformance on silicon
python3 conformance/gf64_conformance_ax7203.py --bit ${DESIGN}.bit
```

**Critical flags**: `-abc9` is required (removal causes 70% → 19% silicon regression). `-nocarry` always. See `fpga/openxc7-synth/Makefile.200t` and `.claude/skills/fpga-synth/SKILL.md` for the full recipe.

Reproducing the LUT measurements (yosys 0.63):

```bash
yosys -p "read_verilog fpga/openxc7-synth/gf_adder_param.v /tmp/gf16_param_top.v; \
          synth_xilinx -abc9 -nocarry -arch xc7; stat"
```

## Key Directories

| Path | Contents |
|------|----------|
| `fpga/openxc7-synth/` | RTL (`gf_adder_param.v`, `tekum16_adder.v`, `gf16_add_top.v`), Makefiles, Docker recipes, XDC constraints |
| `conformance/` | Per-format silicon harnesses (`*_conformance_ax7203.py`), `gf_ref.py` / `tekum_ref.py` golden oracles, batch flash scripts |
| `research/` | `LUT_COMPARISON_MEASURED.md`, `CATALOG_PAPER_DRAFT.md`, `arxiv_submission/`, `head_to_head.py` benchmark |
| `hardware/tools/` | `trinity_flash.py`, `bitstream_provenance.py`, FTDI udev rules |
| `src/trinity_node/` | DePIN attestation (Zig 0.16) — bitstream hash as trust anchor |
| `fpga/CATALOG_MATRIX_83.md` | Live SSOT for the 83-format catalog and HW progress |

## Key Findings

**1. 16 GF compute cells bit-exact on silicon.** GF4, GF6, GF8, GF12, GF16, GF20, GF24, GF32 — ADD and MUL each — pass with 0 failures on AX7203 silicon (2026-07-02 audit). Vector counts vary by run (64–512 sampled; GF4 exhaustive at 256).

**2. GF64 timing closure failure — root cause identified.** Best silicon score 359 / 512 (70.1%). Two independent timing-critical paths in `gf_adder_param`: (a) a 43-bit barrel shifter driven by a 25-bit amount, now clamped to 6 bits (`MANT_BITS+4`); (b) an 8-branch priority encoder over 64-bit data, still too deep for CFGMCLK. Definitive fix is a 2-stage pipeline (decode+shift+sticky → register → add+norm+round+pack).

**3. LUT comparison — measured, not estimated.** Same toolchain (yosys 0.63, `synth_xilinx -abc9 -nocarry -arch xc7`):

| Module | Total LUT | Dynamic range |
|--------|----------:|----------------|
| GF16 (`gf_adder_param`, current) | 486 | 18 decades |
| GF16 (`gf16_add_top`, deprecated) | 176 | — (no denormals/NaN) |
| tekum16 (`tekum16_adder.v`, stub) | 573 | 153 decades |
| takum16 | N/A | RTL adder does not exist |

The current GF16 adder is **0.85×** the tekum16 stub (15% smaller), not "4–11× smaller". The deprecated 176-LUT number (and the stale "118 LUT" from BENCH-005) omitted denormal / NaN / parameterization logic. GF16 and tekum16 occupy **different points on the area-vs-dynamic-range trade-off**: GF16 wins area, tekum16 wins range. Neither dominates. Full table and repro commands in `research/LUT_COMPARISON_MEASURED.md`.

**4. DePIN attestation — bitstream hash as trust anchor.** `src/trinity_node/attestation.zig` binds each deployed bitstream to its provenance record (`hardware/tools/bitstream_provenance.py`) so a node can cryptographically attest that the silicon it runs matches a published, reproducible build. Combined with the openXC7 flow (no vendor EDA), this makes the silicon result independently reproducible and auditable.

## Limitations (honest)

- **SW-bitexact ceiling is 75 / 83**, not 83. The remaining 8 formats are structural / parametric and have no independent decode law to witness against — they need a bit-exact generator, not a port.
- **GF64 does not yet close timing.** 70.1% silicon score; the pipeline fix is designed but not yet proven on hardware.
- **takum16 / takum32 / takum64 have no adder RTL** in this repository — only `takum16_decode.v` exists. Any LUT comparison involving takum is N/A.
- **tekum16 result is a stub** (65% bit-exact, truncation not RNE). A corrected tekum16 with RNE may be larger than 573 LUT.
- **No silicon is pending.** The TTSKY26b tape-out submission was withdrawn and
  there is no fabrication route at present, so nothing here is awaiting a die.
  Any ASIC claim about this work is out of date.
- The `0.85×` LUT ratio compares a production GF16 adder against a non-final tekum16 stub. Treat it as a lower bound on the real ratio, not a victory claim.

Per `research/goldenfloat-positioning.md`: claims are scoped to what was measured, on this toolchain, on this silicon, on this date.

## License

MIT © 2024-2026 Dmitrii Vasilev. See [LICENSE](LICENSE).

## Author

**Dmitrii Vasilev** — ORCID [0009-0008-4294-6159](https://orcid.org/0009-0008-4294-6159), Trinity Research Collective.

## Upstream contributions

Getting these results required fixing the toolchain, not only using it.
**25 patches merged** into openXC7: 23 in `nextpnr-xilinx`, 2 in
`demo-projects`. One is open and two are drafts.

Representative of the class of defect found: a clock-buffer placement search
gave up after 50 000 wires when the buffer it needed was the 75 492nd, so "no
legal placement" meant "did not finish counting"; and `set_multicycle_path
-setup` was parsed but never applied.

Two remain unresolved and are stated as such. A hardware `IDDR` does not deliver
data until the flow writes one ILOGIC configuration bit -- established by A/B/A
reflashing on silicon, reproducible in both directions, but the polarity of the
fix is not established, so that patch is deliberately a draft. And a `BUFR`
divider appears to be ignored; that one is a source reading whose consequence
has never been built or measured, and it says so where it is filed.

## Links

- Catalog paper (this repository): [arXiv:2606.09686](https://arxiv.org/abs/2606.09686)
- GoldenFloat GF16 paper: [arXiv:2606.05017](https://arxiv.org/abs/2606.05017)
- Issues: [github.com/gHashTag/trinity-fpga/issues](https://github.com/gHashTag/trinity-fpga/issues)
- Catalog SSOT: [`fpga/CATALOG_MATRIX_83.md`](fpga/CATALOG_MATRIX_83.md)
- LUT measurements: [`research/LUT_COMPARISON_MEASURED.md`](research/LUT_COMPARISON_MEASURED.md)
