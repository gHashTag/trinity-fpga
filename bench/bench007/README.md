# bench/bench007 — measured clock, step rate and board power on the AX7203

| path | what |
|---|---|
| `rtl/bench_meter.v` | Instrument: DUT clock cycles and step pulses per 1 s window, counted against the 200 MHz crystal, reported over UART as `B7,seq,cycles,steps,xor` lines |
| `rtl/bench007_probe_ax7203.v/.xdc` | Standalone probe: measures CFGMCLK on this die; built-in self-check (steps = cycles/1024) |
| [`.github/workflows/bench007-probe-ax7203.yml`](../../.github/workflows/bench007-probe-ax7203.yml) | GitHub Actions build (openXC7 in Docker, image pinned by digest). Timing must PASS: no `--timing-allow-fail` |
| `host/b7_capture.py` | UART or stdin capture with host timestamps, sealed with sha256 |
| `host/b7_analyze.py` | Self-tests first (with negative controls), then clock, steps, power, ΔP verdict, energy per step → `results/<tag>/results.{json,md}` |
| `sim/` | Icarus testbenches, primitive stubs, synthetic captures, and `run_all.sh` that runs all of it |
| `RUNBOOK.ru.md` | Procedure |
| `MEASURED.template.md` | The report to fill from `results/` |

Re-run every check (5 clock ratios, 3 planted faults that must be caught, the probe top, and the
analysis on synthetic captures with known answers, a broken instrument, a zero delta, one repetition
and a wrong time base):

```
bash sim/run_all.sh        # ends with ALL PASS
```

`bench007_probe_ax7203.bit` + `.sha256` and `build_log/` (yosys, nextpnr, provenance) are the probe
bitstream built from exactly these sources by that workflow (run 35993961960); Run workflow rebuilds it.
