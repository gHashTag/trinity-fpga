# Cron-loop: autonomous FPGA-check of all formats on a local AX7203

> **Source:** drafted by owner 2026-07-03, saved to repo (version-controlled) because
> the skill-write sandbox was down (500: Failed to place sandbox). Promote to the
> `trinity-wave-loop` skill as `references/cron-fpga-flash-loop.md` via `save_custom_skill`
> when sandbox returns. Verified against live HEAD of gHashTag/trinity-fpga (issue #199,
> status 03–04.07.2026): decode-HW 41, compute-HW 30, Tier-E ~71/73, ceiling 73/83,
> board AX7203 IDCODE 0x13636093.

## 0. Invariants (must not be violated)

- **Board:** AX7203 = XC7A200T-2FBG484I, part `xc7a200tfbg484-2`, IDCODE `0x13636093` (NOT `0x0362D093`). Clock 200 MHz LVDS R4(+)/T4(−) → IBUFDS.
- **Tier E is counted ONLY with a complete chain on #199:** (a) CI run URL (bitstream GREEN) + (b) bitstream SHA256 + (c) UART-log `HW RESULT: N/N bit-exact (fails=0)` @160000 baud + (d) confirmed IDCODE `0x13636093`. Missing any one of the four → it is NOT Tier E.
- **encoding ≠ compute ≠ FPGA.** A 2-oracle SW (Python golden == Corona RTL in simulation) is `[verified SW]`, NOT decode-HW. A `sim N/N bit-exact` simulation ≠ HW.
- **Ceiling = 73/83** (10 structural-formats are un-flashable — there is no single-value decode law). Never chase 83/83.
- **The catalog count is an invariant that grows — never hard-code it** (the 84 once quoted was wrong). SSOT = `specs/numeric/formats_catalog.t27` in the t27 repo; `tools/gen_formats_catalog.py` there prints "parsed N formats" (109 formats at v3 of the catalogue paper, Sep 2026). The `/83` ratios in this instruction use the denominator of the 2026-07-03 snapshot it was drafted against.
- **No categorical claims.** Status tags: `[proven]`/`[verified SW]`/`[measured on silicon]`/`[routing-pending]`/`[REQUIRES USER ACTION]`.
- `confirm_action` before any push/merge to a public repo. Synthesis/flashing runs on the user's local machine (outside the sandbox) → always `[REQUIRES USER ACTION]`, the cron cannot flash on its own.

## 1. What the cron CAN and CANNOT do

**Can (without hardware, in the sandbox/via API):**
- Read the state of #199 via `api.github.com` → count current decode-HW / compute-HW / Tier-E.
- Check the status of CI-runs (bitstream GREEN / routing-pending / fail) via `actions/runs`.
- Verify SHA256 and the presence of a UART-proof in comments (anti-fake-pass).
- Prepare the next cell: an RTL-skeleton from a template (track-a decode-port / track-b new-RTL / compute-GF), a golden-oracle (mpmath/Fraction @120-bit, RNE+sticky), a sim-testbench.
- Build a task queue and a Tier-E comment template for the local agent.

**CANNOT (only the local agent on the user's machine):**
- `pld load` of a bitstream, `runtest`, a physical UART-conformance → this is burst-flash, outside the sandbox.
- Promote a cell to Tier E without a real UART-log.

## 2. One atomic cron cycle (every N minutes)

```
INPUT:
  1. fetch api.github.com/repos/gHashTag/trinity-fpga/issues/199 (body + counters)
     + comments?per_page=100&page=1..2 → parse the latest Tier-E proof-comments.
  2. Reconcile the live count: decode-HW, compute-HW, Tier-E total, ceiling 73.

ACTION (depth-first, priority in order):
   A. Check routing-pending cells (takum32/64, lns16 re-flash):
      - if the CI run went GREEN + there is a SHA256 → ready to flash → into the queue for the local agent.
      - if the CI is still running → [routing-pending], skip.
   B. If there is a Tier-C cell (sim-verified, bitstream exists, no UART) →
      build a flash-task + a Tier-E comment template.
   C. Otherwise take the next UN-flashed format from the catalog of 83 depth-first
      (the compute-GF family earlier than breadth-decode) → prepare an RTL-skeleton
      + golden-oracle + sim-testbench, launch CI-synth (docker-retry, per-seed
      --signal=KILL timeout).

GATE (anti-fake-pass, falsifier rule):
   - Promote a cell to Tier E ONLY at 4/4 (CI GREEN + SHA256 + UART N/N fails=0 + IDCODE).
   - sim-bitexact ≠ HW. Never count a simulation as HW.
   - If the UART-log is missing → the cell stays Tier C, the cron does NOT touch the count.

OUTPUT:
   - If a NEW Tier-E cell with full proof appeared → send_notification (format, count N/83, CI URL).
   - If nothing new → end the run silently (without notification).
   - If 2+ [BACKGROUND CRON FAILED] in a row for one reason → do NOT keep hammering, leave the
     instruction as is (user: do NOT stop the cron, only improve the instruction).
```

## 3. Burst-flash template for the local agent (AX7203, outside the sandbox)

The cron puts this into a task for the local agent; the agent does the flash itself on the machine:

```
# 0. Unlock JTAG on LIBUSB_ERROR_ACCESS:
pkill -f openocd; sudo kextunload -b com.apple.driver.AppleUSBFTDI 2>/dev/null; # + power-cycle the board if persistent
# 1. Atomic step per format:
openocd -f <cfg> -c "init; pld load 0 <format>.bit; runtest 10000; exit"   # flash the bitstream
<uart_conformance_runner> --port /dev/cu.usbserial-120 --baud 160000 | tee logs/<format>_hw.log
# 2. Descriptor-leak stop-rule: pkill -f openocd every ~5 cycles.
# 3. fmt-codes decode 0–12 (tf32 = 7-byte frame). Tier E publication:
gh issue comment 199 --repo gHashTag/trinity-fpga --body "<template below>"
```

**Tier-E comment template:**

```
### Tier-E proof: `<format>` (decode|compute)
decode-HW N->N+1. Tier-E M.
- CI run: https://github.com/gHashTag/trinity-fpga/actions/runs/<id>
- Bitstream SHA256: `<sha256>`
- IDCODE: `0x13636093` ✅ | Flash: <s>s, rc=0
- UART conformance: `HW RESULT: N/N bit-exact (fails=0)` @160000 baud, /dev/cu.usbserial-120
```

## 4. Stop-rule and honesty

- The cron stops promotion at **73/83** (the ceiling). Beyond that only the SW-track (69→73 in t27) and correctness-fixes of already-proven cells.
- A discrepancy in public numbers (e.g. catalog 83 vs preprint 84) → prepare an erratum, do not silently correct.
- Every claimed jump in the count the cron must reconcile via API (`gh`/`api.github.com`) before accepting it — the lesson of "checking the wrong repo → a false commit-not-found".

## 5. Pending owner actions (when sandbox returns)

- [ ] Save this file as `references/cron-fpga-flash-loop.md` in the `trinity-wave-loop` skill via `save_custom_skill`.
- [ ] Create issue about dead nf4-kernel in `gHashTag/trios-trainer-igla` (draft approved, English body).
- [ ] Save `igla-race-format-benchmark.md` reference (repo map of trios-*, two BPB cuts — frozen champion + live matrix-ledger, falsifier_2-warning, top format tables, API-fallback patterns).
- [ ] Bind to cron: see recommendation below.
