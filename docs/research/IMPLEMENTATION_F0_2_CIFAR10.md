# F0.2: CIFAR-10 Cross-Stack Validation Implementation

**Status:** Ready to implement

## Overview

F0.2 validates GF16 format against competing formats (FP16, BF16) using CIFAR-10 dataset instead of MNIST. This provides scientific credibility beyond synthetic MNIST benchmarks.

## Architecture

```
Dataset: CIFAR-10 (10k images, 32x32x3 RGB, 10 classes)
Model: Small CNN — Conv(3→16)→ReLU→Pool → Conv(16→32)→ReLU→Pool → FC(1152→128) → FC(128→10)
Formats compared: GF16, FP16, BF16
Output: results/cifar10_metrics.json
```

### Architecture Details

- **Input:** 32×32×3 = 3072 features (RGB images)
- **Conv1:** 3 channels → 16 filters, 3×3 kernel, stride=1, padding=1
- **Pool1:** 2×2 max pooling, stride=2 → output 16×16×16 = 4096
- **Conv2:** 16 channels → 32 filters, 3×3 kernel, stride=1, padding=1
- **Pool2:** 2×2 max pooling, stride=2 → output 8×8×32 = 2048
- **FC1:** 2048 → 128 dense layer
- **FC2:** 128 → 10 output layer (softmax)

### Baseline Expected Accuracy

Small CNN without data augmentation on CIFAR-10: **~70-75%**

## Implementation Notes

### 1. Build System Integration
The Zig build system uses explicit `b.step()` calls. The `bench_cifar10` executable needs proper registration in build.zig.

**Current issue:** build.zig expects steps like `const bench_XXX_step = b.step("...", "...")` pattern. We're using a simpler approach.

### 2. Model Weights
CIFAR-10 requires a trained small CNN for CIFAR-10. Options:
- Train from scratch in PyTorch (small CNN architecture as above)
- Export weights in binary format (compatible with F0.2 loader)
- Use cross-entropy loss, Adam optimizer, 50-100 epochs

### 3. CIFAR-10 Dataset
The loader at `src/cifar10_loader.zig` downloads from:
`https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz`

This is 10k images (32x32x3 RGB), requires downloading (~160MB).

## Phase 2 Summary (Complete)

- Competitive analysis documents copied to docs/research
- arXiv + GitHub research completed (30+ papers, multiple repos analyzed)
- Issue #497 updated with findings

**Next Phase:** 3. Experimental Directions (academic paper, hardware bridge, optimizer suite)

---

**Document Status:** Created implementation plan for F0.2.
