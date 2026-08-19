# Against a published reference implementation, at last (W937)

Every posit row in the manuscript is the author's own structural model, and the
field's de facto posit hardware baseline — PACoGen (Jaiswal & So, IEEE Access
2019) — is cited **zero** times in 7,858 lines. So the question "is the advantage
a property of the format or of the comparator?" had no answer.

PACoGen is Verilog, so it runs through the same local flow as everything else.
Both sides measured with the W936 replication rig: instantiate N times in a
pipelined chain, fit `cells(N) = fixture + cost·N` at N = 1,2,4,8, metric
LUT + CARRY4, `yosys 0.63`, `synth_xilinx -nodsp`. Record:
[`head_to_head_w937.json`](head_to_head_w937.json), rig
[`rig_ext.py`](rig_ext.py).

## Decode

| unit | cells/decode | R² |
|---|---:|---:|
| PACoGen `data_extract_v1`, N=16, es=2 | **92.000** | 1.00000 |
| this tree's `posit16_decode` | **125.000** | 1.00000 |
| this tree's `TNF16` decode | **2.000** | 1.00000 |

**Our posit baseline is not inflated.** It costs 1.36× the reference's extraction
stage — and it does strictly more work, since PACoGen's extract emits
`(rc, regime, exp, mant)` while ours assembles a full fp32. The paper's posit
decode numbers are therefore defensible against the field's reference, which is
the single most valuable thing this comparison could have shown.

Against the reference implementation rather than against our own model, the
decode separation is **92 / 2 = 46×**.

## Operator — the number that shrinks

| unit | cells/adder | R² |
|---|---:|---:|
| PACoGen `posit_add`, N=16, es=2 | **693.000** | 1.00000 |
| `tnf_cost_e4m8_add_top` (E_t = 4, M = 8, **16 physical cells**) | **561.670** | 0.999999 |

**TNF's adder is 1.23× cheaper than the reference posit16 adder.** Not 6×. Not
46×. Twenty-three percent, at matched storage width, against a published
implementation, under one flow.

That is the honest operator-level number, and it deserves to be the headline
rather than a decode ratio: a real system pays for operators, and the decode
advantage is amortised the moment anything is done with the decoded value.

Increments per step were 563, 563 and 560.75 cells — the N=8 point sits 9 cells
below the line, so a little cross-instance sharing happens at depth 8; the fitted
561.67 is reported rather than the 563 the first two steps suggest.

## What is matched and what is not

- **Matched:** storage width (16 cells both sides), synthesiser, options, metric,
  rig, part family, and the fact that both are *someone's* implementation rather
  than an estimate.
- **Not matched:** microarchitecture. `posit_add` is combinational with a `start`
  input; `gf_adder_param` carries valid/ready handshaking, so some of its area is
  control that PACoGen does not have — the 1.23× is therefore a **lower bound** on
  the datapath advantage and an upper bound on the system advantage.
- **Not established:** correctness of either side in this run. PACoGen ships
  testbenches that were not executed here; the TNF core's conformance lives in the
  project's own suite. A wrong operator is a cheap operator.
- **Not post-route.** Synthesis cells only.

## The one line to take away

The paper currently claims **6.1× over posit32** from decoder models it wrote
itself. The measured, matched-width, reference-implementation comparison at the
operator level is **1.23×** — and it is real, checkable and nobody else has run it.

---

*φ² + φ⁻² = 3 | TRINITY*
