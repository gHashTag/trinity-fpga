# Trinity-FPGA

**Number formats, proven bit-exact on live silicon, with a toolchain that has no vendor licence in it — and 28 upstream patches that made that toolchain able to do it.**

An 83-entry catalogue of numeric formats — IEEE binary16/32/64/128, posits, takums, Galois-field floats GF4–GF64, IBM/Cray/VAX historical formats, MX variants, LNS — each synthesised through `yosys` + `nextpnr` (openXC7) for the Artix-7 XC7A200T, flashed to a real board, and checked against an independent software oracle until every bit agrees.

No Vivado. No licence server. Runs on a Mac.

---

## What is here that is not elsewhere

### 1. 28 merged patches to the open-source Xilinx toolchain

Getting these results meant fixing the tools, not just running them. **26 merged in [openXC7/nextpnr-xilinx](https://github.com/openXC7/nextpnr-xilinx/pulls?q=is%3Apr+author%3AgHashTag+is%3Amerged)**, **2 in [openXC7/demo-projects](https://github.com/openXC7/demo-projects/pulls?q=is%3Apr+author%3AgHashTag+is%3Amerged)**. That count is verifiable by clicking those links — it does not require trusting anything in this repository.

They are real defects, not typo fixes. A clock-buffer placement search gave up after 50 000 wires when the buffer it needed was the 75 492nd, so "no legal placement" actually meant "did not finish counting" (#110). `set_multicycle_path -setup` was parsed and then never applied (#109). An `IDELAYCTRL` with no delays aborted the build instead of warning (#137). A `BUFR` emitted BYPASS regardless of the divide the design asked for (#151).

One is deliberately **not** merged, and says why. A hardware `IDDR` does not deliver data until the flow writes one ILOGIC configuration bit — established by A/B/A reflashing on silicon, reproducible in both directions — but the polarity of the fix is not established, so it stays a draft.

### 2. Bit-exact on real silicon, with witnesses

Not simulation, not an estimate: a bitstream on an AX7203 board (IDCODE `0x13636093`), fed vectors over UART at 160000 baud, every result compared against an independent oracle.

Recomputed by the repository's own tool, [`research/measure_tier_e_cells.py`](research/measure_tier_e_cells.py), rather than counted once by hand:

- **72 distinct (format, operation) cells** proven on silicon, over **49 distinct base formats**
- of 226 proof comments, **75 carry all four required links** — CI run URL, SHA-256, UART log, IDCODE
- **compute: ADD, MUL and SUB across GF4–GF32**, every cell individually proof-backed

"Tier-E" is this project's own bar and it is deliberately high: a dedicated proof post, the hardware IDCODE and CI run ID, and a bit-exact UART witness captured from the board. Board evidence is in [`fpga/evidence/`](fpga/evidence/) — see [`gf16_add_hw_replay_20260704.md`](fpga/evidence/gf16_add_hw_replay_20260704.md) for a complete chain. (The TSV files under `conformance/witness/` are SoftPosit and libtakum *software* reference dumps, not board captures.)

A figure of "71 / 83" appeared here earlier and is withdrawn: it added 41 decode *formats* to 30 compute *operations* and double-counted gf10 and gf14, against a denominator of formats. The tool above is the source now, because it can be recomputed.

The scale behind that: **107 per-format silicon harnesses**, **23 software oracles**, **110 CI workflows** of which **70 drive the openXC7 image**.

### 3. Reproducible without any hardware, in one command

```bash
make oracle
```

**18 oracle self-tests, 0 failures**, no board and no FPGA tooling. That is the floor of the whole stack: if the oracles do not agree with themselves, nothing downstream means anything.

### 4. A published catalogue paper

[arXiv:2606.09686](https://arxiv.org/abs/2606.09686) v2 — the 83-format catalogue. Companion GF16 format paper: [arXiv:2606.05017](https://arxiv.org/abs/2606.05017).

---

## Status

Counts are traceable to the file named beside them. Where two internal sources disagreed, the lower figure is printed and the disagreement is stated rather than resolved by preference.

| Axis | Count | Source |
|------|-------|--------|
| Upstream patches merged | **28** | 26 nextpnr-xilinx + 2 demo-projects, verifiable on GitHub |
| Cells proven on silicon | **72** (format, operation) pairs | `research/measure_tier_e_cells.py`, read live from issue #199 |
| — distinct base formats | **49** | same tool |
| — proofs with all four links | 75 of 226 | CI URL + SHA-256 + UART log + IDCODE |
| SW bit-exact | **69 / 83** | `fpga/CATALOG_MATRIX_83.md`; a strict recount gives 62 — see limitations |
| Oracle self-tests | 18 pass, 0 fail | `make oracle`, run 2026-08-18 |
| Catalogue paper | published | [arXiv:2606.09686](https://arxiv.org/abs/2606.09686) v2 |
| `zig build` | **fails** | see [Known-broken](#known-broken) |

---

## Try it

```bash
git clone --recursive https://github.com/gHashTag/trinity-fpga.git
```

`external/zig-golden-float` (numerical core) and `external/tt-trinity-corona` (decode RTL) are submodules; a plain clone leaves them empty.

### Reproduce — no hardware, no submodule

```bash
make oracle   # 18 oracle self-tests
make repro    # cross-validate oracles across format families
make bench    # accuracy vs an exact Fraction oracle
make lut      # GF16 LUT count (requires yosys)
```

These are the parts that work from a plain clone.

### Build and flash a bitstream — needs Docker and an AX7203

```bash
docker run --rm regymm/openxc7 bash -c '
  yosys -p "read_verilog gf_adder_param.v ${DESIGN}.v; \
            synth_xilinx -abc9 -nocarry -arch xc7; write_json ${DESIGN}.json"
  nextpnr-xilinx --chipdb /chipdb-xc7a200tfbg484-2.bin \
            --json ${DESIGN}.json --xdc ${DESIGN}.xdc --write ${DESIGN}.rpt
  fasm2frames ${DESIGN}.fasm > ${DESIGN}.frames
  xc7frames2bit --frm_file ${DESIGN}.frames --bit_file ${DESIGN}.bit'

sudo openocd -f fpga/openxc7-synth/ax7203_al321.cfg -c "init; pld load 0 ${DESIGN}.bit; exit"
python3 conformance/gf64_conformance_ax7203.py --bit ${DESIGN}.bit
```

**`-abc9` is mandatory.** Removing it costs a 70% → 19% silicon regression. `-nocarry` always. Full recipe: [`fpga/openxc7-synth/Makefile.200t`](fpga/openxc7-synth/Makefile.200t) and [`.claude/skills/fpga-synth/SKILL.md`](.claude/skills/fpga-synth/SKILL.md).

---

## Known-broken

Stated up front, because it makes documented instructions fail.

**`zig build` does not resolve.** Under the Zig 0.16.0 in this environment it stops at
`build.zig:2869: no field or member function named 'linkSystemLibrary' in 'Build.Step.Compile'` — a
0.15 → 0.16 API break on a raylib GUI target. Seven `linkSystemLibrary` call sites remain, plus
three each of `addIncludePath` and `addCSourceFile` that the same migration will reach.

This note has a shelf life and has already expired once: it named `build.zig:69` and `linkLibC`
until 2026-08-18, when those eight sites were migrated to `root_module.link_libc` and the next
break surfaced one layer down. A "known-broken" line is a claim like any other — date it, name the
exact line, and re-run the command before trusting it.

Nothing above this line depends on
it: the oracles, the conformance harnesses and the bitstream flow are Python and Verilog.

---

## Where the pipeline actually lives

Worth being precise, because the repository looks self-contained and is not:

| Part | Where |
|---|---|
| Orchestration, CI, measurement harnesses | here — 110 workflows, 70 driving the openXC7 image |
| RTL, constraints, conformance oracles | here — [`fpga/`](fpga/), [`conformance/`](conformance/) |
| `yosys`, `nextpnr-xilinx`, `prjxray` | the `regymm/openxc7` Docker image, pinned by digest |
| Fixes to those tools | upstream, in openXC7's repositories |
| Numerical core (GF16, TF3, VSA) | `external/zig-golden-float` submodule |
| Catalogue status | [`fpga/CATALOG_MATRIX_83.md`](fpga/CATALOG_MATRIX_83.md) |
| Measurement records, LUT comparison, paper | [`research/`](research/) |
| Flashing, bitstream provenance, FTDI rules | [`hardware/tools/`](hardware/tools/) |

Everything is reproducible from a pinned image digest; nothing about the toolchain is vendored here. That is deliberate — patches go upstream where others get them — and it is why the merged-patch count is in the status table rather than a footnote.

---

## Limitations

Stated because they are true, not because they are small.

- **SW bit-exact is 69 / 83, and a strict recount gives 62.** An earlier figure of 75 stood in this README; it is withdrawn. Four internal sources including the catalogue matrix say 69, and one of them prescribed this correction on 2026-07-14 and was never applied. The remaining formats are structural or parametric with no independent decode law to witness against; they need a bit-exact generator, not a port.
- **The catalogue matrix enumerates 19 formats in table form**, the rest carried in prose summaries. It is the best source available and is not yet a per-format table for all 83.
- **GF64 does not close timing.** Best silicon score 359 / 512 (70.1%). Two critical paths identified — a 43-bit barrel shifter driven by a 25-bit amount, and an 8-branch priority encoder over 64-bit data. The 2-stage pipeline fix is designed, not yet proven on hardware.
- **GF16 does not beat tekum16 on area by the margin once claimed.** On one toolchain (yosys 0.63, `synth_xilinx -abc9 -nocarry -arch xc7`): GF16 486 LUT / 18 decades against tekum16 573 LUT / 153 decades — 0.85×, 15% smaller, not "4–11× smaller". Different points on the area-versus-range trade-off; neither dominates. The tekum16 side is a stub (65% bit-exact, truncation not RNE) and a corrected version may be larger. Details: [`research/LUT_COMPARISON_MEASURED.md`](research/LUT_COMPARISON_MEASURED.md).
- **`takum16/32/64` have no adder RTL here** — only `takum16_decode.v`. Any LUT comparison involving takum is N/A.
- **No silicon is pending.** The TTSKY26b tape-out submission was withdrawn and there is no fabrication route at present. Any ASIC claim about this work is out of date.

The rule this project holds itself to: never write "measured" for something that was not measured, and when a number is withdrawn, grep for the number rather than for the file you remember writing it in.

---

## License

MIT © 2024–2026 Dmitrii Vasilev. See [LICENSE](LICENSE).

## Author

**Dmitrii Vasilev** — ORCID [0009-0008-4294-6159](https://orcid.org/0009-0008-4294-6159), Trinity Research Collective.
