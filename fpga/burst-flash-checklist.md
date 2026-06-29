# Burst Flash Checklist — AX7203 decode/compute cell verification

> Reusable reference for any agent driving a flash burst on AX7203 (XC7A200T-2,
> IDCODE `0x13636093`). Each cell follows the same 7-step sequence. A cell reaches
> **Tier E** (full evidence chain) ONLY when ALL 7 steps are completed and the
> UART log is posted to the tracking issue (#199). Missing step 5 (publication) =
> **Tier C** (self-report only).

## Prerequisites
- JTAG accessible: `sudo openocd -f fpga/openxc7-synth/ax7203_al321.cfg -c "init" -c "shutdown"` → must print IDCODE `0x13636093` (no `LIBUSB_ERROR_ACCESS`).
- UART accessible: `/dev/cu.usbserial-120` (CP2102N, 160000 baud).
- Bitstream + conformance script exist locally (see tables below).

## §1 — Flash the bitstream
```bash
sudo openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" \
  -c "pld load 0 <BITSTREAM_PATH>" \
  -c "runtest 200000" \
  -c "shutdown"
```
Verify: IDCODE `0x13636093` printed (not `LIBUSB_ERROR_ACCESS`). Load takes ~78s.

## §2 — Run conformance (UART verify)
```bash
# Decode cells:
python3 conformance/corona_decode_host_ax7203.py --port /dev/cu.usbserial-120 --baud 160000 --fmt <N>

# Compute cells:
python3 conformance/gf<N>_add_conformance_ax7203.py --port /dev/cu.usbserial-120 --baud 160000
```
Expected: `N/N bit-exact, fails=0`.

## §3 — Record evidence
- CI run ID (that built the bitstream).
- Bitstream SHA256.
- UART result line (`N/N bit-exact`).

## §4 — Verify IDCODE after flash
```bash
# Re-probe after flash to confirm the FPGA is alive:
sudo openocd -f fpga/openxc7-synth/ax7203_al321.cfg -c "init" -c "shutdown"
# Must print IDCODE 0x13636093
```

## §5 — Publish UART log to #199 (REQUIRED for Tier E)
Post a comment on the tracking issue with:
- Cell name (format + column: decode-HW / compute-HW)
- CI run ID + bitstream SHA256
- UART result line (copy-paste from §2 stdout)
- IDCODE confirmation (§4)
Without this step → **Tier C** only (self-report, no public evidence).

## §6 — Update matrix in epic body / experience log
Increment the measured count for the column. Tag: `[измерено на железе, Tier E]`.

## §7 — Commit experience log update
```bash
git add fpga/experience/wave-loop-*.trinity.md
git commit -m "feat(fpga): <format> <column> Tier E measured on AX7203"
git push
```

---

## Decode cells (9 prepared, bitstreams in build/corona_*)

| Format | fmt# | Bitstream | Coverage |
|---|---|---|---|
| posit8 | 4 | build/corona_posit8/corona_decode_ax7203.bit | 256 exhaustive |
| fp8_e5m2 | 5 | build/corona_fp8-e5m2/corona_decode_ax7203.bit | 256 exhaustive |
| fp4_e2m1 | 6 | build/corona_fp4/corona_decode_ax7203.bit | 16 exhaustive |
| int4 | 7 | build/corona_int4/corona_decode_ax7203.bit | 16 exhaustive |
| fp6_e2m3 | 8 | build/corona_fp6-e2m3/corona_decode_ax7203.bit | 64 exhaustive |
| fp6_e3m2 | 9 | build/corona_fp6-e3m2/corona_decode_ax7203.bit | 64 exhaustive |
| lns8 | 10 | build/corona_lns8/corona_decode_ax7203.bit | 256 exhaustive |
| tf32 | 11 | build/corona_tf32/corona_decode_ax7203.bit | 8 corners (7-byte frame) |
| binary16 | 12 | build/corona_binary16/corona_decode_ax7203.bit | 8 corners |

Note: tf32 uses a 7-byte request frame (3 code bytes); others use standard 6-byte.
binary16 golden uses struct 'e' (NaN payload propagated, not canonical).

## Compute cells (6 prepared, gf20 Docker-deferred)

| Format | Bitstream | Conformance | Coverage |
|---|---|---|---|
| gf4 | build/gf4_fixed/gf4_clean_ax7203.bit | gf4_add_conformance_ax7203.py | exhaustive 256 |
| gf12 | build/gf12_clean/gf12_clean_ax7203.bit | gf12_add_conformance_ax7203.py | 512 §3.5 |
| gf16 | build/gf16_param/gf16_clean_ax7203.bit | gf16_add_conformance_ax7203.py | 512 §3.5 (HAS_INF=1) |
| gf24 | build/gf24_clean/gf24_clean_ax7203.bit | gf24_add_conformance_ax7203.py | 480 §3.5 |
| gf20 | (Docker Hub CI pull hangs — 6 attempts) | gf20_add_conformance_ax7203.py | 480 §3.5 |
| gf6 | build/gf6_dl/gf6-clean-bitstream/gf6_clean_ax7203.bit | (already Tier E measured) | 512/512 |
| gf8 | build/gf8_sp/gf8-clean-bitstream/gf8_clean_ax7203.bit | (already Tier E measured) | 512/512 |

Note: gf6/gf8 are ALREADY measured Tier E (posted on #199). The burst only needs
to flash gf4/gf12/gf16/gf24 (+ gf20 when its bitstream builds).
