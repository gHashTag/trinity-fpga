# Trinity-FPGA: 83 Number Formats on Open-Source Silicon

This repository proves numerical number formats on open-source FPGA tooling. Each format in the 83-entry catalog is synthesized through `yosys` + `nextpnr` (openXC7) for the Artix-7 XC7A200T (AX7203 board), flashed to silicon, and checked bit-exact against an independent software oracle. The catalog spans IEEE floats (binary16/32/64/128), posits, takums, Galois-field floats (GF4–GF64), IBM/Cray/VAX historical formats, MX variants, and LNS — every entry measurable, reproducible, and attestable on commodity hardware without a paid EDA license.

## Status

Snapshot 2026-08-18. Counts are measured, not projected.

| Axis | Count | Notes |
|------|-------|-------|
| SW-bitexact | 75 / 83 | Ceiling reached; remaining 8 are structural (no independent decode law) |
| decode-HW Tier-E | 41 / 83 | UART @160000 on AX7203, IDCODE `0x13636093` |
| compute-HW Tier-E | 16 cells | GF4–GF32 × {ADD, MUL}, 0 failures on silicon (vectors vary by run) |
| GF64+ on silicon | 70.1% | 359 / 512 score; two timing paths identified, fix in progress |
| Catalog paper | Published | [arXiv:2606.09686](https://arxiv.org/abs/2606.09686) v2, 83 formats |
| Upstream patches merged | 28 | 26 in [openXC7/nextpnr-xilinx](https://github.com/openXC7/nextpnr-xilinx/pulls?q=author%3AgHashTag), 2 in demo-projects; 1 draft open |
| `tri` CLI | **Does not build** | No build definition in the tree — see [Known-broken](#known-broken) |

Tier-E = rigorous evidence: dedicated proof post, hardware IDCODE + run ID, bit-exact UART witness on silicon. See `fpga/CATALOG_MATRIX_83.md` for the live SSOT.

## Known-broken

Stated up front, because both defects make documented instructions fail:

**`git clone --recursive` does not work.** The tree pins `external/zig-golden-float` at gitlink `c7af4bbe`, and that commit is not on the remote — nor is `1923572c`, which local checkouts hold. The numerical core exists only on machines that already have it. Until those commits are pushed, or the gitlink re-pinned to something reachable, a fresh clone cannot fetch the submodule.

**The `tri` CLI does not compile.** It imports twelve named modules (`sacred`, `tvc_corpus`, `trinity_swe`, `vsa`, …) that only a `build.zig` can supply, and there is no `build.zig`: it became `build.zig.tri` in `ac4304f78` and that file was deleted by `4d57ad02c`. The old definition — 4208 lines, 295 modules — is recoverable from `ac4304f78`, and all but one of the sources it names still exist (`src/vsa.zig` is gone; `HRR` now lives in `external/zig-golden-float/src/vsa/hrr.zig`). Every `tri …` command in the documentation therefore describes intent, not a working tool.

Two smaller repairs are in: 366 lines of dead farm code that referenced a file extracted to another repository in April, and `src/tri/mutex.zig`, which absorbs the `std.Thread.Mutex` (0.15) / `std.atomic.Mutex` (0.16) split so the 78 call sites compile under either.

## Quick Start

### Reproduce results (no hardware, no submodule)

```bash
make oracle   # 12 oracle self-tests (72 formats)
make repro    # cross-validate oracles (7 format families)
make bench    # accuracy benchmark vs exact Fraction oracle
make lut      # GF16 LUT count (requires yosys) — expect ~491 LUT
```

These are the parts that work from a plain `git clone`.

### Build a bitstream (Docker + AX7203)

```bash
docker run --rm regymm/openxc7 bash -c '
  yosys -p "read_verilog gf_adder_param.v ${DESIGN}.v; \
            synth_xilinx -abc9 -nocarry -arch xc7; write_json ${DESIGN}.json"
  nextpnr-xilinx --chipdb /chipdb-xc7a200tfbg484-2.bin \
            --json ${DESIGN}.json --xdc ${DESIGN}.xdc --write ${DESIGN}.rpt
  fasm2frames ${DESIGN}.fasm > ${DESIGN}.frames
  xc7frames2bit --frm_file ${DESIGN}.frames --bit_file ${DESIGN}.bit
'
sudo openocd -f board/ax7203.cfg -c "init; pld load 0 ${DESIGN}.bit; exit"
python3 conformance/gf64_conformance_ax7203.py --bit ${DESIGN}.bit
```

**Critical flags**: `-abc9` is required (removal causes 70% → 19% silicon regression). `-nocarry` always. Full recipe in `fpga/openxc7-synth/Makefile.200t` and `.claude/skills/fpga-synth/SKILL.md`.

## Where the pipeline actually lives

Worth being precise, because the repository looks self-contained and is not:

| Part | Where |
|---|---|
| Orchestration, CI, measurement harnesses | here — 108 workflows, 60 of them driving the openXC7 image |
| RTL, constraints, conformance oracles | here — `fpga/`, `conformance/` |
| `yosys`, `nextpnr-xilinx`, `prjxray` | the `regymm/openxc7` Docker image, pinned by digest |
| Fixes to those tools | upstream, in openXC7's repositories |
| Numerical core (GF16, TF3, VSA) | `external/zig-golden-float` submodule |

Everything is reproducible from a pinned image digest; nothing about the toolchain is vendored here. That is deliberate — patches go upstream where others get them — and it is why the merged-patch count above is part of the status table rather than a footnote.

## Key Directories

| Path | Contents |
|------|----------|
| `fpga/openxc7-synth/` | RTL, Makefiles, Docker recipes, XDC constraints |
| `conformance/` | Per-format silicon harnesses, golden oracles, batch flash |
| `research/` | LUT comparison, catalog paper draft, arXiv submission, probes |
| `hardware/tools/` | `trinity_flash.py`, `bitstream_provenance.py`, FTDI udev rules |
| `fpga/CATALOG_MATRIX_83.md` | Live SSOT for the catalog and HW progress |

## Key Findings

**1. 16 GF compute cells bit-exact on silicon.** GF4, GF6, GF8, GF12, GF16, GF20, GF24, GF32 — ADD and MUL each — pass with 0 failures on AX7203 (2026-07-02 audit). Vector counts vary by run (64–512 sampled; GF4 exhaustive at 256).

**2. GF64 timing closure failure — root cause identified.** Best silicon score 359 / 512 (70.1%). Two independent timing-critical paths in `gf_adder_param`: a 43-bit barrel shifter driven by a 25-bit amount, now clamped to 6 bits; and an 8-branch priority encoder over 64-bit data, still too deep for CFGMCLK. Definitive fix is a 2-stage pipeline.

**3. LUT comparison — measured, not estimated.** Same toolchain (yosys 0.63, `synth_xilinx -abc9 -nocarry -arch xc7`):

| Module | Total LUT | Dynamic range |
|--------|----------:|----------------|
| GF16 (`gf_adder_param`, current) | 486 | 18 decades |
| GF16 (`gf16_add_top`, deprecated) | 176 | — (no denormals/NaN) |
| tekum16 (`tekum16_adder.v`, stub) | 573 | 153 decades |
| takum16 | N/A | RTL adder does not exist |

The current GF16 adder is **0.85×** the tekum16 stub, not "4–11× smaller". GF16 and tekum16 occupy different points on the area-vs-range trade-off; neither dominates. Repro commands in `research/LUT_COMPARISON_MEASURED.md`.

**4. DePIN attestation — bitstream hash as trust anchor.** `src/trinity_node/attestation.zig` binds each deployed bitstream to its provenance record, so a node can attest that the silicon it runs matches a published, reproducible build.

## Limitations (honest)

- **SW-bitexact ceiling is 75 / 83.** The remaining 8 are structural and need a bit-exact generator, not a port.
- **GF64 does not close timing.** 70.1% silicon score; the pipeline fix is designed, not proven.
- **takum16 / takum32 / takum64 have no adder RTL** here — only `takum16_decode.v`. Any takum LUT comparison is N/A.
- **tekum16 is a stub** (65% bit-exact, truncation not RNE). A corrected version may be larger than 573 LUT.
- **No silicon is pending.** The TTSKY26b tape-out was withdrawn and there is no fabrication route at present.
- The `0.85×` ratio compares a production GF16 adder against a non-final stub. Lower bound, not a victory.

Per `research/goldenfloat-positioning.md`: claims are scoped to what was measured, on this toolchain, on this silicon, on this date.

## Upstream contributions

Getting these results required fixing the toolchain, not only using it. **28 patches merged** into openXC7 — 26 in `nextpnr-xilinx`, 2 in `demo-projects`.

Representative of the class: a clock-buffer placement search gave up after 50 000 wires when the buffer it needed was the 75 492nd, so "no legal placement" meant "did not finish counting"; `set_multicycle_path -setup` was parsed but never applied; and a placed `BUFR` received no configuration at all — not `IN_USE`, not its divider — because the emission rode on a routing pseudo-pip that a placed cell never crosses.

One remains unresolved and is stated as such. A hardware `IDDR` does not capture: both outputs are inert while the pin demonstrably carries traffic. Vendor golden bitstreams have since eliminated the site configuration as the explanation — the entire emission difference against Vivado is four `IFF.ZSRVAL_Q` bits that a design with `R` and `S` tied low should never load. That is reasoning awaiting a silicon A/B, and the patch stays a draft until it has one.

## License

MIT © 2024-2026 Dmitrii Vasilev. See [LICENSE](LICENSE).

## Author

**Dmitrii Vasilev** — ORCID [0009-0008-4294-6159](https://orcid.org/0009-0008-4294-6159), Trinity Research Collective.

## Links

- Catalog paper: [arXiv:2606.09686](https://arxiv.org/abs/2606.09686)
- GoldenFloat GF16 paper: [arXiv:2606.05017](https://arxiv.org/abs/2606.05017)
- Issues: [github.com/gHashTag/trinity-fpga/issues](https://github.com/gHashTag/trinity-fpga/issues)
- Catalog SSOT: [`fpga/CATALOG_MATRIX_83.md`](fpga/CATALOG_MATRIX_83.md)
- LUT measurements: [`research/LUT_COMPARISON_MEASURED.md`](research/LUT_COMPARISON_MEASURED.md)
