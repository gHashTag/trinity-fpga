# IHP Open PDK — Free MPW Tapeout Application
## Trinity GF16 Ternary Neural Core
### To: open-pdk@ihp-microelectronics.com

---

**Subject:** Trinity GF16 Ternary Neural Core — MPW Submission Request (SG13G2)

Dear IHP Open PDK Team,

We are submitting a request to participate in the next IHP SG13G2 MPW shuttle with an open-source ternary neural inference core.

## Project: TrinityASIC-0

### What we built

We have designed and **FPGA-validated** a ternary neural network inference core based on GF16 (Golden Float 16-bit) φ-quantization. The core uses **zero hardware multipliers** — inference is performed entirely via XOR + popcount operations over ternary weights {-1, 0, +1}.

| Metric | Value |
|---|---|
| Architecture | VSA ternary matmul 64×64 |
| Quantization | GF16 (φ-distance = 0.048633) |
| Hardware multipliers | **0** (pure XOR + popcount) |
| FPGA validation | 64/64 iverilog PASS, 21/21 cargo test GREEN |
| FPGA speedup | 135x vs CPU baseline |
| Power (FPGA) | ~5W on XC7A100T |
| Projected ASIC power | ~0.3W @ 28nm, ~0.05W @ SG13G2 |
| Model | IGLA Champion (BPB=0.1427, 73K params, fineweb) |
| RTL License | Apache 2.0 (fully open) |
| Toolchain | Rust + Yosys + nextpnr + openFPGALoader |

### Repository

https://github.com/gHashTag/trinity-fpga

Key files:
- `fpga/vsa/vsa_matmul.v` — ternary matmul core (FPGA-validated)
- `fpga/vsa/vsa_bind.v`, `vsa_unbind.v`, `vsa_bundle.v` — VSA ops
- `bitstream/igla_champion_gf16.bin` — GF16 weights (144KB)
- `docs/arxiv-trinity-stack-draft.md` — arXiv draft (in progress)

### Why SG13G2 fits perfectly

1. **Pure digital design** — no analog, no RF. SG13G2 BiCMOS digital layer is sufficient
2. **Small area** — 64×64 ternary matmul + 144KB SRAM ≈ 1–2 mm² estimated
3. **No DSP blocks needed** — XOR gates only, standard cells sufficient
4. **Open EDA toolchain** — we use Yosys for synthesis, compatible with OpenLane2
5. **Unique design** — GF16 φ-quantization (φ²+φ⁻²=3) not previously fabricated

### ASIC target specifications

```
Core:       64×64 ternary MAC array (XOR + 6-bit popcount)
Weights:    144KB SRAM (igla_champion_gf16.bin)
I/O:        UART TX (tokens output), SPI (weight loading)
Frequency:  target 200–500 MHz
Power:      target < 0.1W
Area:       target < 2 mm²
Process:    SG13G2 (130nm BiCMOS)
```

### Team

- Lead: gHashTag (GitHub) — Rust/RTL/FPGA
- Stack: fully open-source, Apache 2.0
- Location: Ko Samui, Thailand (timezone UTC+7)

### Academic output

arXiv draft in preparation:
*"Trinity Stack: φ-Structured GF16 Ternary Inference on $30 FPGA and Path to Open ASIC"*
- cs.AR (Hardware Architecture)
- cs.LG (Machine Learning)

### Request

We request:
1. **One MPW slot** in the next SG13G2 shuttle
2. Technical guidance on Caravel-equivalent wrapper for SG13G2
3. Information on PDK design rules for our standard-cell ternary array

We are prepared to:
- Submit complete GDS2 within the shuttle deadline
- Publish all results openly on GitHub
- Present at IHP open-source workshop if invited

Thank you for the IHP Open PDK initiative — it makes research like ours possible.

Best regards,  
Trinity Stack Team  
https://github.com/gHashTag/trinity-fpga

---
*Generated from trinity-fpga/docs/funding/IHP-MPW-application.md*
