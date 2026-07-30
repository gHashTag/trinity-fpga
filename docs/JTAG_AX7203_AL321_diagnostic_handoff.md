# AX7203 / AL321 JTAG — diagnostic handoff for the local HW agent

> Campaign: Task C (takum32/64 IDCODE+UART) + Task A (gf48/64/96/128 UART) on the
> connected AX7203. Prepared 2026-07-30 after the sandbox agent hit a flashing
> blocker. This file consolidates **what is already verified** (do not re-check)
> and a 4-step escalation plan. Rule: **do not repeat the same failing approach
> more than 2 times** — escalate to the next step.

## Board + toolchain (verified present)
- Board: ALINX AX7203 = Xilinx `xc7a200tfbg484-2`. JTAG IDCODE **0x13636093** —
  **confirmed by a clean `openocd` probe** (JTAG tap works).
- Cable: AL321 (FT2232H, vid 0x0403 pid 0x6014). Config:
  `fpga/openxc7-synth/ax7203_al321.cfg` (adapter speed 100 kHz — "the only stable
  speed for this cable"; higher → garbage IDCODEs / MPSSE hangs).
- UART (for conformance after flash): `/dev/cu.usbserial-1110` @160000.
- `openocd` present; `yosys` 0.63 present; `nextpnr-xilinx` **ABSENT** (no new
  bitstream builds — only flash pre-built `.bit`).

## Bitstreams already staged (`/tmp/bitstreams/`, downloaded from CI runs of 2026-07-08/09)
| format | run_id | SHA-256 |
|--------|--------|---------|
| takum32 | 28935841570 | `eb402381aa458979cca9c1a3b646888d16bdf6ea14c54af67ac5e13f170b0e48` |
| takum64 | 28959783877 | `e486019acae5cd2ffcf2b3045b640a38a1c3b36981e7cc68040249a162b730d3` |
| gf48 | 28995969962 | `f4b03bc6fce9b783bcc7b215cc30d6b0576f2058935f89254d3cfaa67b03e378` |
| gf64 | 28995971004 | `833703113e5da60ec8685407874aea348024769eec12295388c0ce099718625a` |
| gf96 | 28995972098 | `63a8c2a2be996bb1abf7cbdb80f467534593a825d37bcaf22e04d52172fc9dbf` |
| gf128 | 28995973373 | `ccc4e5ae1497e97840d4c0f47632a3d185db85709ff388c677340879983cca00` |

## Already verified — do NOT re-investigate
1. **No FTDI kext is loaded** (`kextstat | grep ftdi` empty) → `kextunload` is a
   dead end, there is nothing to unload.
2. **`sudo` requires a password** (no NOPASSWD) → cannot `kextunload`
   non-interactively on this machine.
3. **`LIBUSB_ERROR_ACCESS` is BENIGN on macOS** — the IDCODE probe succeeded
   despite it. It is NOT the cause of the flashing failure. Do not chase it.
4. **Symptom:** `openocd … -c "pld load 0 /tmp/bitstreams/takum32.bit" …` produces
   **no output for >17 minutes** at the locked 100 kHz adapter speed. Two runs
   were killed by timeout (180 s, 1020 s). Bitstream ≈ 9.7 MB ⇒ at 100 kHz the
   raw floor is ~13 min, so the open question is **slow vs. real MPSSE hang**.

## 4-step escalation plan

### Step 1 — distinguish "slow" from "hang" (decisive; do first)
Run with full debug + a ≥20 min window so progress (or freeze) is visible:
```
openocd -d2 -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" -c "pld load 0 /tmp/bitstreams/takum32.bit" \
  -c "runtest 2000" -c "shutdown" 2>&1 | tee /tmp/jtag_takum32.log
```
- If bytes/progress advance over time and it completes ⇒ **slow**, not hung.
  Then just allow ~15 min/bitstream for the remaining 5.
- If output freezes at the same point twice ⇒ **real MPSSE hang** → go to Step 3.

### Step 2 — adapter-speed / driver sanity (only if Step 1 inconclusive)
- Cautiously try `adapter speed 50` (more stable) and verify the `virtex2` pld
  driver is the one used (`openocd -d2` logs the PLD driver). The cfg warns
  >100 kHz corrupts IDCODEs on this cable — do not exceed 100 kHz without
  re-confirming IDCODE 0x13636093 after.

### Step 3 — openFPGALoader alternative (if openocd truly hangs)
openFPGALoader is generally more reliable than openocd for Xilinx bitstream load.
Install if needed and try:
```
openFPGALoader -b alinx_ax7203 /tmp/bitstreams/takum32.bit   # or --ft2232-type ... 
```
Find the right board/cable flags for the AL321 (FT2232H). If it loads → use it
for all 6, then return to openocd only if needed for IDCODE read-back.

### Step 4 — once a bitstream loads: capture the 4/4 Tier-E chain
For each format: flash → run the decode-conformance host script on
`/dev/cu.usbserial-1110` → capture `HW RESULT: N/N bit-exact (fails=0)` → record
**SHA-256** (above) + **IDCODE 0x13636093** + the **CI run URL** → write the full
4/4 chain to issue #199 via `gh api repos/gHashTag/trinity-fpga/issues/199/comments -f body=...`.
- takum32 host: `conformance/takum32_decode_conformance_ax7203.py --port /dev/cu.usbserial-1110`
  — needs `/tmp/t27_ssot/conformance/vectors/takum32_conformance_v0.json` (a
  minimal staged copy exists; replace with the canonical SSOT vector if available).
- gf48/64/96/128: `conformance/test_all_77_hw.sh` (expects `/tmp/bitstreams/${fmt}.bit`).
- The host scripts check UART only — SHA-256 and IDCODE must be captured separately.

## Reminders (binding)
- IDCODE 0x13636093 is silicon-fixed (same for every bitstream) — one clean read
  satisfies the Task-C IDCODE requirement; per-bitstream IDCODE is a sanity re-check.
- Keep three metrics separate: RTL-generated ≠ yosys-PASS([simulated]) ≠ Tier-E 4/4.
- No "first/best/only". Status tags required. Do not move the Tier-E counts
  retroactively — only after a clean 4/4 chain is posted.
- The old "71/83" headline was a decode+compute **cell sum**, not format-coverage;
  #199 @2026-07-15 retracted it (`"71/83" was WRONG`). Real union (decode ∪
  compute) ~49-55/83. Don't re-introduce 71/83 as a coverage figure.
- If after Step 1 the verdict is "real hang" and Steps 2–3 don't resolve it,
  report back; the alternative path is installing `nextpnr-xilinx` and rebuilding
  bitstreams (unblocks Task D/E/B too).
