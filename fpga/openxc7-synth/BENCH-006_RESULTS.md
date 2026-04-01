# BENCH-006: MAC-level FPGA Cost Comparison

## Status: ✅ COMPLETE (Fair MAC-level comparison)

### What's New (vs BENCH-005)

BENCH-005 measured **single operations**. BENCH-006 measures **MAC blocks** (dot-product units), which reflects real neural network inference cost.

---

## Synthesis Results (Yosys)

| Module | Cells | LUT | FF | DSP | LC Est | Status |
|--------|-------|-----|----|-----|--------|--------|
| **ternary_mac_16** | 71 | 52 | 69 | 0 | 52 | ✅ Synthesis OK |
| **gf16_mac_16** | 549 | 71 | 266 | **16** | 549 | ✅ Synthesis OK |

### Detailed Breakdown

**Ternary MAC-16**:
- LUT3: 4, LUT4: 21, LUT5: 12, LUT6: 15 = **52 LUT**
- FF: 69 (FDCE)
- Carry chains: 2× CARRY4
- No DSP blocks used (as expected for ternary)

**GF16 MAC-16**:
- **16× DSP48E1** (all 16 multipliers use DSP slices)
- FF: 266 (FDCE)
- Total cells: 549
- LUT count: 71 (LUT1=3, LUT2=2, LUT3=8, LUT4=21, LUT5=12, LUT6=14, LUT7=11)

---

## Interpretation

### 1. Unit-level vs MAC-level cost

| Level | Ternary LUT | GF16 LUT | Ratio | DSP |
|-------|-------------|----------|-------|-----|
| **Add (single)** | 2 | 118 | 59× | 0 vs 0 |
| **Mul (single)** | 2 | 94 | 47× | 0 vs 1 |
| **MAC-16 (16×)** | 52 | 71 | **1.37×** | 0 vs **16** |

### 2. Key Findings

1. **Ternary MAC-16: 52 LUT, 69 FF, 0 DSP**
   - Simple adder tree (no multipliers needed)
   - Expected: ternary MAC = adder tree + sign logic
   - No DSP blocks used (pure LUT logic)

2. **GF16 MAC-16: 549 cells, 16× DSP48E1, 266 FF**
   - **All 16 DSP blocks used** (one per multiply)
   - Each GF16 multiplier maps to DSP48E1 slice
   - Significant register file for pipeline stages

3. **DSP utilization**
   - Ternary: 0 DSP (no multipliers)
   - GF16: 16 DSP (one per element-wise multiply)
   - Ratio: **∞** (ternary uses no DSP, GF16 uses 16 of 240)

4. **Parallel capacity on XC7A100T**
   - Ternary MAC-16: 52 LUT → **~1,219** parallel units (63,400 / 52)
   - GF16 MAC-16: 71 LUT → **~893** parallel units (logic-limited)
   - DSP limited: 240 DSP / 16 per MAC = **15** parallel GF16 MAC-16 units (DSP is bottleneck)

---

## Comparison: Unit vs MAC

| Metric | Ternary | GF16 | Ratio |
|--------|---------|------|-------|
| **Single add** | 2 LUT | 118 LUT | 59× |
| **Single mul** | 2 LUT | 94 LUT + 1 DSP | 47× |
| **MAC-16** | 52 LUT | 71 LUT | **1.37×** |
| **DSP usage** | 0 | 16 (per MAC) | ∞ |

**Note**: GF16 MAC-16 LUT count extracted via JSON parsing: **71 LUT** (LUT1=3, LUT2=2, LUT3=8, LUT4=21, LUT5=12, LUT6=14, LUT7=11).

---

## Files Generated

| File | Purpose |
|------|---------|
| `ternary_mac_16.v` | Ternary 16-element dot product |
| `gf16_mac_16.v` | GF16 16-element dot product |
| `ternary_mac_16.json` | Yosys synthesis (71 cells, 52 LUT) |
| `gf16_mac_16.json` | Yosys synthesis (549 cells, 16 DSP) |

---

## Next Steps

1. ✅ Parse JSON for exact LUT count (gf16_mac_16.json) — COMPLETE: 71 LUT
2. Run P&R (nextpnr-xilinx) for Fmax measurement
3. Compare against HSLM full pipeline (4,267 LUT)
4. Document: "GF16 MAC-16 uses 16× DSP, ~893 parallel units (logic-limited), ~15 units (DSP-limited) on XC7A100T"

---

## References

- [Wiley 2018](https://onlinelibrary.wiley.com/doi/10.1002/cta.3834) — Custom FP formats: 10¹–10² LUT per operator
- [arXiv:1910.12625](https://arxiv.org/pdf/1910.12625.pdf) — Ternary MAC: add/sub/skip, no true multiplier
- [MDPI Electronics](https://www.mdpi.com/2079-9292/13/14/2838) — Dot product FPGA implementation
