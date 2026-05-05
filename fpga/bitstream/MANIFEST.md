# Bitstream Manifest — Trinity S³AI FPGA

**φ² + φ⁻² = 3** | trios#380 App.F

## Device

| Field | Value |
|---|---|
| Board | QMTech XC7A100T Starter Kit |
| Actual die | **XC7A200T** (IDCODE `0x13631093`) |
| Silicon rev | 1 |
| Package | FGG484 |
| Tool | Vivado 2023.2 |

## Bitstream

| Field | Value |
|---|---|
| File | `design.bit` |
| SHA-256 | `8536e265...d77352b` *(full hash in CI artefact)* |
| LUT used | 83 / 134,600 (0.06%) |
| FF used | 27 / 269,200 (0.01%) |
| BRAM | 0 |
| DSP | 0 |

## Configuration Status Register

```
Raw STAT: 0x401079FC

DONE      = 1  ✅
EOS       = 1  ✅  (End Of Startup)
GWE       = 1  ✅  (Global Write Enable)
GHIGH_B   = 1  ✅
MMCM_LOCK = 1  ✅
DCI_MATCH = 1  ✅
CRC_ERR   = 0  ✅
ID_ERR    = 0  ✅
DEC_ERR   = 0  ✅
```

## Programming Command

```bash
openFPGALoader --cable xvc-client \\
  --ip 192.168.1.30 --port 2542 \\
  --bitstream design.bit

# Verify:
openFPGALoader --cable xvc-client \\
  --ip 192.168.1.30 --port 2542 \\
  --read-register STAT
# Expected: 0x401079FC
```

## Date

2026-05-05 22:00 +07 (Ko Samui)
