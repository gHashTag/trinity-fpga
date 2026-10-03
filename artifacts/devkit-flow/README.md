# devkit-flow.gif — `tri devkit flow` and `impact`, recorded

`devkit-flow.cast` is an asciicast v2 recording of one session on 2026-10-03
(04:31 UTC), made with `tri cast record`. No board was used.

1. `tri devkit flow --build --out /tmp/devkit-flow/rec1` exited 0. It ran the
   openXC7 flow for `trinet_node_v2_ax7203` on `xc7a200tfbg484-2`
   (`tri fpga-build`, 121,587 FASM lines), then `bitwalk --fasm` and
   `bitwalk --write` on the same FASM, 3 runs each, and compared both outputs
   with openXC7's: frames and .bit byte-identical.
2. `tri devkit impact --out /tmp/devkit-flow/rec1 --builds 20` exited 0.

| Layer | openXC7 tool | Time | Share | t27 | Time | Same bytes |
|---|---|---:|---:|---|---:|---|
| L1 synthesis | yosys | 12.69 s | 10.9 % | not yet | – | – |
| L2 place & route | nextpnr-xilinx | 70.09 s | 60.0 % | not yet | – | – |
| L3 FASM → frames | fasm2frames.py | 33.86 s | 29.0 % | bitwalk --fasm | 0.42 s | yes |
| L4 frames → .bit | xc7frames2bit | 0.22 s | 0.2 % | bitwalk --write | 0.25 s | yes |
| Whole flow | | 116.86 s | | with L3 + L4 in t27 | 83.45 s | 1.40× |

Amdahl ceilings, the whole flow if one more layer took 0 s: L1 → 70.76 s
(1.65×), L2 → 13.36 s (8.75×). These are bounds, not results. At an assumed
20 builds a day, one person, 230 working days, the measured 33.4 s a build is
42.7 hours a year. The builds, people and days are assumptions.

Wall seconds on one laptop at a 1-minute load of 12.6 on 8 cpus. The openXC7
times come from the build; the t27 times are the best of 3 runs right after it.
The .bit's SHA-256 is `2b016e53…dde1fff`.

`devkit-flow.gif` is `tri cast render` of the cast with `--max-idle 2`
(1043×740, 65 frames). The same recording is published at
`https://t27.ai/term/devkit-flow/` (`tri cast publish`) and used by the
TRI DEV KIT page, `https://t27.ai/#/devkit`.

**Staged:** the prompt and the key-by-key typing of each command.

**Real:** every byte the commands printed, at the time they printed it.

**Edited:** the home directory is shown as `~` (`tri cast scrub`). Nothing
else was changed.

**Shortened:** any silence longer than 2 s is shown for 2 s, with a note on
that frame. The real session took 127.4 s; the GIF runs 17.2 s.
