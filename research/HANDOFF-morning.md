# What needs a person — hand-off

Written at loop iteration 031, after three consecutive iterations with no
external change. Everything that could be done without a decision has been.
This file exists so acting takes minutes rather than a search through a long
conversation.

---

## 1. ~~Push `zig-golden-float`~~ — DONE, and the diagnosis here was wrong

**Fixed in `f2925251`. `git clone --recursive` works; verified by actually
cloning.** Both submodules populate at their pinned SHAs.

Recording the error, because the prescription in this section would have wasted
the reader's time and not fixed anything.

It said to push the submodule. **There was nothing to push.** The local checkout
`1923572c` is already an ancestor of the submodule's `origin/main` — it is a
hundred commits *behind* it, not ahead. `git push origin HEAD` would have
reported "Everything up-to-date" and the clone would have kept failing.

The real fault was one level up: `main` pinned the gitlink at `c7af4bbe`, and
that object does not exist on the server.

```
$ git fetch --depth=1 https://github.com/gHashTag/zig-golden-float c7af4bbe...
fatal: remote error: upload-pack: not our ref c7af4bbe...
```

Nor is it reachable from any remote branch — after fetching every branch it is
still absent locally. So the fix was to repoint the gitlink at `1923572c`, which
is fetchable, is what the working copy has always used, and is what the
`trinet-fleet-truth` branch already pinned. Not a guess: the version the tree
has actually been built against.

Deliberately **not** bumped to the submodule's current `origin/main`. That is a
hundred-commit upgrade with real risk and belongs in its own change.

`external/tt-trinity-corona` was checked by the same method and was always fine.

**The lesson worth keeping.** This section asserted two things — "`c7af4bbe` is
not on the remote" (true) and "`1923572c` is not on the remote either" (false) —
and prescribed a fix that followed only from the false half. Both claims were
written from the same glance at the same output. The test that settled it,
`git fetch <url> <sha>`, takes one second and returns an unambiguous
`not our ref`.

*Two* checks failed along the way while writing this, both reporting success:
`set -- $pair` does not word-split in zsh, so a loop testing both submodules ran
`git fetch` with empty arguments and printed `FETCHABLE ✓` for both; and `$?`
after a pipeline captures `tail`, not `git`. Same family as everything in
`.claude/skills/stale-reference/SKILL.md` §12 — when a check cannot fail, its
output is indistinguishable from a pass.

---

## 2. The #114 board experiment — the last standing hypothesis

Site configuration is **eliminated**. Vendor goldens showed the entire emission
difference at the IDDR site is four `IFF.ZSRVAL_Q` bits that a design with `R`
and `S` tied low should never load. That is reasoning, not measurement, and it
needs the AX7203.

**No rebuild of nextpnr required.** The edit is at FASM level:

```bash
grep -c 'ZSRVAL_Q' design.fasm && grep -v 'IFF.ZSRVAL_Q' design.fasm > design_nozsrval.fasm
```

Then assemble both and flash A/B/A:

```bash
docker run --rm -v "$PWD:/w" regymm/openxc7 bash -c 'source /prjxray/env/bin/activate; for f in design design_nozsrval; do fasm2frames --part xc7a200tfbg484-2 --db-root /nextpnr-xilinx/xilinx/external/prjxray-db/artix7 /w/$f.fasm > /w/$f.frm && xc7frames2bit --part_name xc7a200tfbg484-2 --frm_file /w/$f.frm --output_file /w/$f.bit; done'
```

**Reading the result.** If capture starts without those bits, the cause is found
and the nextpnr fix is small — make the `ZSRVAL` loop conditional on the `SR`
port actually being driven. If capture stays dead, the hypothesis is closed and
the emission space is exhausted: the cause is then clock routing into the ILOGIC
or the ILOGIC itself, not site configuration.

Either outcome is publishable. Check `sudo -n true` first — NOPASSWD does not
survive a reboot.

---

## 3. Two decisions that are yours, not urgent

**The 395 unreachable files.** `research/src-tri-reachability.md` measures them;
the ratchet stops the count growing but deletes nothing. Some may be someone's
unfinished work. A one-pass static analysis is not grounds for removing 3 MB.

**Risky commands in CI.** Smoke coverage is 18 of 144. The rest need either
subcommand invocations with valid arguments, or a decision that commands like
`deploy`, `serve` and `clean` may run on a runner. I judged the static safety
classifier unsound and abandoned it — see skill §12.

---

## 4. Waiting on other people, for reference

| who | what | where |
|---|---|---|
| @hansfbaier | differential-clock question; whether to take the coverage gate as a PR | openXC7/nextpnr-xilinx#154 |
| @hansfbaier | merge `openXC7/prjxray-db#7` — reviewed and independently checked, no objection | prjxray-db#7 |
| either | whether to regenerate 6 of 8 `demo-projects` goldens so #120 can merge | #120 |

`047b` is **delivered** — see §6.

---

## 5. Drafts — both now sent

Nothing is waiting to be sent. For the record of what went where:

* the retraction of the timing-column correction — the harness passes `--freq`
  explicitly and emits no timing verdict at all — is committed as
  `research/benchmark-timing-correction.md`;
* the figure that retraction did **not** catch has since been corrected too:
  `65.5–69.7 MHz` mixed a placement estimate with a routed value. The routed
  pair is **68.73 / 69.72**, identical across all five runs of each design
  (pinned seed). Corrected on nextpnr-xilinx#150.

Three corrections to one number, all the same cause: quoting a figure without
opening the file it came from. Any future statement of it should name the log
line — 1515 and 1512 in `max-frequency-lines.txt`.

---

## 6. Delivered since this file was written (2026-08-19)

**@cavearr closed out `047b`, and his own prediction with it.** The I2IOCLK
position of the DMUX sets no bit — it is the default. Four `default` pseudo-pips,
not a segbits campaign. Site→DMUX map now measured: `Y0↔2, Y1↔3, Y2↔0, Y3↔1`.

Two PRs up: **openXC7/prjxray-db#7** (segbits +8, ppips: four wrong `always`
retired, four `default` added) and **openXC7/prjxray#8** (extended 039).

I resolved the probe's features against both databases by hand — Docker is down
here, and this is a static check, not an assembled frame:

| feature | published db | with prjxray-db#7 |
|---|---|---|
| `…IO_PLL_CLK0_DMUX.HCLK_IOI_I2IOCLK_TOP0` | unresolved | `default` |
| `BUFIO_Y1.IN_USE` | unresolved | `37_16 37_18` |
| `HCLK_IOI_RCLK2IO3.HCLK_IOI_CK_BUFRCLK3` | `always` — resolves, sets nothing | `28_17` |
| `BUFR_Y0.BUFR_DIVIDE.D5` | has bits | unchanged |

The third row is the important one: it resolved *before*, silently contributing
no bits. Assembles clean, regional clock never arrives — #150's class exactly.

**And the finding that was nobody's prediction:** all 36 `BUFR_DIVIDE` rows are
already in the published database and the PR touches none of them. The divide
ladder was fully characterised with no modelled path in or out. Coverage counted
per primitive would have scored BUFR as done — which is why row counts are not
coverage.

**Filed: nextpnr-xilinx#155** — `create_clock` is not propagated through
`IBUF`/`BUFG` and PLL/MMCM outputs are not derived, so every design reports
`PASS` against the 12 MHz default. Carlos's diagnosis, credited there.

**Still yours:** the AX7203 A/B in §2, and the `zig-golden-float` push in §1.
Neither moved.

**Open decision:** PR #613 carries three `.sh` harness files against this repo's
no-shell-scripts rule. They are measurement provenance, not tooling. Reviewed
with two required README edits (link #155; add the VexRiscv dead-bitstream
caveat covering ten of the twenty rows). The merge is yours.
