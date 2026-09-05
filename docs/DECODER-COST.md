# The isolated decode cost, measured by replication (W936)

The comparison this project has been arguing about ranks formats whose cost over a
shared fixture is 0–2 LUT against a one-LUT quantum ([`HARNESS-FLOOR-W936.md`](HARNESS-FLOOR-W936.md)).
This report removes the fixture entirely instead of arguing about how to subtract it.

## Method

Each decoder is instantiated **N times in a pipelined chain** inside the same
harness — stage *i* consumes stage *i−1*'s registered output, so inputs differ
per stage (no common-subexpression elimination), only the last stage is folded
into the LED (observation cost constant in N), and the pipeline registers land in
FF rather than in logic. Synthesise at N = 1, 2, 4, 8 and least-squares fit

    cells(N) = fixture + cost · N

The slope is the per-decoder cost; the fixture falls out as the intercept and
never has to be subtracted by hand. Local `yosys 0.63`, `synth_xilinx -nodsp`,
generator `gen_replicated.py` (committed alongside this report).

**Metric is LUT + CARRY4.** The first run counted LUT1–LUT6 and MUXF7/8 only and
reported TNF16/32/64 at **0.000** — a perfect fit (R² = 1.00000) around a wrong
number, because `tnf16_decode` is a constant add that yosys maps entirely onto a
carry chain. A perfect fit measures an instrument's consistency, never its
completeness (lesson 1407).

## Result

| format | (LUT+CARRY4)/decoder | of which LUT | CARRY4 | fixture | R² |
|---|---:|---:|---:|---:|---:|
| `int8` | **0.000** | 0 | 0 | 34.0 | 1.00000 |
| `GFTernary` | **2.000** | 2 | 0 | 36.0 | 1.00000 |
| `TNF16` | **2.000** | 0 | 2 | 36.0 | 1.00000 |
| `TNF32` | **2.000** | 0 | 2 | 36.0 | 1.00000 |
| `TNF64` | **2.000** | 0 | 2 | 36.0 | 1.00000 |
| `binary32` | 5.000 | 5 | 0 | 39.0 | 1.00000 |
| `BNF16` | 10.000 | 8 | 2 | 44.0 | 1.00000 |
| `fp8 e4m3` | 12.000 | 8 | 4 | 46.0 | 1.00000 |
| `fp8 e5m2` | 12.000 | 8 | 4 | 46.0 | 1.00000 |
| `GF10` | 26.000 | 24 | 2 | 60.0 | 1.00000 |
| `minifloat` | 31.000 | 27 | 4 | 65.0 | 1.00000 |
| `GF14` | 36.000 | 35 | 1 | 70.0 | 1.00000 |
| `VAX F` | 41.000 | 39 | 2 | 75.0 | 1.00000 |
| `binary16` | 54.000 | 51 | 3 | 88.0 | 1.00000 |
| `GF+8` | 56.348 | 50.6 | 6 | 110.7 | 0.99731 |
| `posit16` | 125.000 | 112 | 13 | 159.0 | 1.00000 |
| `IBM hex32` | 129.000 | 126 | 3 | 163.0 | 1.00000 |
| `LNS16` | 159.000 | 149 | 10 | 193.0 | 1.00000 |
| `posit32` | 304.000 | 281 | 23 | 338.0 | 1.00000 |

Eighteen of nineteen fits are exact to five decimals with integer slopes. `GF+8`
is the sole exception (R² = 0.99731) — something in it is not perfectly linear in
N, and that is worth its own look rather than a smoothing.

## What this settles

**The ternary exponent field is 5× cheaper to decode than the binary one.**
`bnf_decode.v` states that BNF and TNF differ *exactly* in binary-versus-ternary
exponent field, and the isolated costs are **10.000 vs 2.000**. The mechanism is
visible in eight lines of Verilog: BNF carries `(e == 0) ? 0 : e − 63 + 127`, a
subnormal special case that costs 8 LUT; TNF's offset needs no special case and
resolves to a bare constant add on the carry chain. This is the paper's central
comparison, isolated for the first time, at R² = 1.

**The cost is width-independent for TNF.** TNF16, TNF32 and TNF64 all measure
2.000 with identical fixtures — the decode does not grow with the format's width,
which no table in the paper currently shows.

**The separations that matter are enormous and unambiguous:** TNF against fp8
**6×**, against posit16 **62×**, against LNS16 **80×**, against posit32 **152×**.
None of these is near any noise band this project has measured. The 10.2 % the
paper leads with is not in this league and never was.

**`int8` decodes for free** — 0.000, exactly, as it must: the "decode" is
sign-extension and wiring. Any comparison that puts int8 in the same column as a
format with a real decoder is measuring the harness around them, not them.

## What this does NOT settle

- **Synthesis, not place-and-route.** These are yosys cell counts before mapping,
  packing and routing. They are the right instrument for *relative decode cost*
  and the wrong one for Fmax or slice occupancy.
- **Decoders, not datapaths.** A cheap decoder can sit in front of an expensive
  multiplier. This measures the decode step the paper's tables actually vary.
- **Correctness is not established here.** The manuscript marks eight baselines
  "not swept" and three known-incorrect. **A wrong decoder is a cheap decoder**,
  so every row here inherits its source's verification status, and the honest
  reading is: these are the costs of *the decoders as implemented in this tree*.
- **One synthesiser.** No Vivado cross-check exists; the openXC7 substrate is
  uncalibrated against a vendor flow.

## Reproducing

```bash
cd fpga/tnet && python3 gen_replicated.py . /tmp/rep "1,2,4,8"
```

Machine-readable output: [`decoder_cost_w936.json`](decoder_cost_w936.json) —
every point, every fit, both the LUT-only and the LUT+CARRY4 series.

---

*φ² + φ⁻² = 3 | TRINITY*
