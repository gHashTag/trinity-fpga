# Release v0.2-igla-fpga

## Components

| File | Description | SHA-256 |
|------|-------------|---------|
| `bitstream/igla_champion_gf16.bin` | GF16 weights (BPB=0.1427, 8 tensors, 73,728 params) | `de2719b5...` |
| `fpga/vsa/vsa_matmul.v` | 64x64 ternary matmul kernel (XOR + popcount, 0 DSP48) | — |
| `fpga/vsa/vsa_matmul_top.v` | Synthesizable top: autoregressive inference + UART | — |
| `fpga/vsa/vsa_matmul_top.xdc` | Pin constraints for QMTECH XC7A100T-1FGG676C | — |

## Architecture

```
seed_token ─> Embedding ROM ─> VSA MatMul (64x64) ─> Argmax ─> UART TX
                                   │
                          bind (ternary multiply)
                          + popcount (+1/-1)
                          = signed dot product
                          0 DSP48 blocks
```

## Benchmark (CPU reference)

```
CPU ternary matmul (64x64):     9,255 tokens/sec
FPGA estimate (81.25 MHz):  1,250,000 tokens/sec
Speedup:                      135x
```

## Synthesis

```bash
trios-fpga synth-vsa --output-dir build/vsa_matmul
```

## Flash

```bash
trios-fpga flash --bitstream build/vsa_matmul/vsa_matmul_top.bit --board XC7A200T
```

## Status

```bash
trios-fpga status --xvc-host 192.168.1.100
```

## Verification

- `cargo test --workspace`: 21/21 PASS
- `iverilog tb_vsa_matmul`: 64/64 PASS
- `cargo clippy --workspace`: 0 warnings

phi^2 + phi^-2 = 3 | TRINITY
