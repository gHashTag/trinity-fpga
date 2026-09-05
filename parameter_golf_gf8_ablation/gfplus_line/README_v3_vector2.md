# GF+A v3 — vector 2: downstream-aware pocket-selection metric (loop 22.07.2026)

`[measured — SW proxy, CPU]` (micro-LM) + a pod-script for `[measured — GPU]` (29M, owned by the user).
seed=20260722. Harnesses `testE_v3.py`, `testE_v3_holdout.py`; pod `../../webterm_gfplus_v2select.py`.

## The problem vector 2 closes

v1/v2 (inv. #15/#17) select a pocket by **pure weight MSE** `Σ(w−q(w))²`.
But the downstream error of a layer is given by the **output** error: `‖Wx − q(W)x‖²`. With
calibration activations X the contribution of the error of weight `W_ij` is weighted by the layer's
Hessian diagonal `H_jj = E[x_j²]` (the column-importance method from OBQ/GPTQ). Downstream-aware
selection:

```
carman* = argmin_p  Σ_j H_jj · (W_ij − q_p(W_ij))²      # weighted MSE
```

## Three sub-directions (implemented)

- **2a — sensitivity-selection** (`gfplus_adaptive_v3.py: gfplus_a_v3(metric='hess')`):
  Hessian diagonal `hutchinson_diag_from_acts(X) = E[x_j²]` instead of the uniform metric.
- **2b — honest comparison:** both metrics (MSE / Hessian) are evaluated by **one** downstream
  metric — the SQNR of the layer **output** `Y=X·Wᵀ`, not the weight MSE (otherwise the comparison
  is unfair, the lesson of the v1→v2 bug).
- **2c — holdout ablation** (`testE_v3_holdout.py`): pocket selection is computed on **calib**
  activations, evaluated on **independent val** activations. Otherwise Hessian-selection overfits to
  the calibration set.

## Result (micro-LM, 2 layers W1 192→256, W2 256→65)

### 2b — in-sample (selection and evaluation on the same activations)
Hessian-selection changes the decision for dozens of rows, but the downstream-ΔSQNR is
**non-constant in sign**: bright positives (W2 N6 K8 **+1.130 dB**, W2 N4 K1 +0.534) neighbor
negatives (W2 N8 K1 −0.516).

### 2c — holdout (honest, selection on calib / evaluation on val) — MAIN CONCLUSION
| | value |
|---|---|
| mean ΔSQNR_val (Hessian − MSE) across 12 cells | **+0.055 dB** |
| median | **+0.010 dB** |
| sign-balance | **7 better / 3 worse / 2 equal** |
| maximum | W2 N6 K8 **+1.123 dB** |
| minimum | W2 N8 K1 **−0.867 dB** |

**Honest verdict `[measured — SW proxy, CPU]`:** downstream-aware (Hessian) pocket selection
**on average helps slightly, but is non-constant and within noise** — on uniform micro-LM weights
it does **NOT pay off robustly**. Weight MSE turns out to be a decent downstream surrogate on this
model. There are individual layers (W2 6-bit) with a real gain >1 dB — a signal that on layers with
strongly non-uniform input importance (attention-projections of large models) the gain may be larger.

## GPU-confirmation on 29M — hypothesis CONFIRMED `[measured — GPU, seed=42]`

`research/gfplus_line/webterm_gfplus_v2select.py` (RTX PRO 4500 Blackwell, torch 2.11.0+cu128, 9L d=512,
3000 steps FineWeb, 27 Linear) captured real activations via forward-hooks,
compared MSE-selection vs Hessian-selection by downstream-SQNR on holdout. Full summary —
`v2select_gpu_29M_seed42.md`.

| bits | mean ΔSQNR | median | better/worse/equal |
|---|---|---|---|
| 4  | **+0.878 dB** | +0.080 | 16/1/1 |
| 6  | **+0.697 dB** | +0.234 | 18/0/0 |
| 8  | **+0.680 dB** | +0.170 | 18/0/0 |

**Key point:** the gain is LOCALIZED in deep `linear1` (FFN up-proj) and GROWS with depth:
`l.0.linear1` +0.008 dB → `l.8.linear1` **+3.102 (4b) / +2.155 (6b) / +1.825 (8b)**.
`linear2` (down-proj after activation) gains little (+0.01…+0.36). The mechanism = non-uniformity
of column importance in deep FFNs — something ABSENT in the uniform micro-LM.

**The conclusion inverts the micro-LM:** downstream-aware (Hessian) GF+A pocket selection ≥
MSE-selection by output SQNR in 52 of 54 cells; the margin grows with depth/heterogeneity.

Launch (set env BEFORE python; the first run ~5 min installs torch cu128 and re-execs once):

```
curl -s https://raw.githubusercontent.com/gHashTag/trinity-fpga/main/webterm_gfplus_v2select.py -o /tmp/v2.py
STEPS=3000 python3 /tmp/v2.py
```

## Boundaries (BINDING)

- 1 micro-LM (2 layers), 2 GPU-layers not yet run;
- the downstream metric = the SQNR of the layer output (a linear surrogate), NOT full model-BPB;
- H_jj = the DIAGONAL approximation of the Hessian (like OBQ/GPTQ), not the full second order;
- the +0.055 dB mean gain is below the visual significance threshold — claiming "downstream
  selection improves GF+A" is NOT allowed without GPU confirmation; honestly: "on average neutral
  on the micro-LM, with rare gains >1 dB on individual layers".

## Artifacts

- `gfplus_adaptive_v3.py` — `gfplus_a_v3` (metric mse/hess), `hutchinson_diag_from_acts`, `output_sqnr_db`;
- `testE_v3.py` + `testE_v3_results.json` — in-sample comparison (2a+2b);
- `testE_v3_holdout.py` + `testE_v3_holdout_results.json` — holdout ablation (2c);
- `../../webterm_gfplus_v2select.py` — pod-script for GPU-confirmation on 29M.
