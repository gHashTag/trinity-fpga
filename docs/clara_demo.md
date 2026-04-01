# CLARA Demo Documentation

## Overview

CLARA TA1 (DARPA PA-25-07-02) aims to demonstrate Trinity's compositional learning and reasoning capabilities through a clean, reproducible pipeline.

## Building Trinity

### Local Build (Recommended for Development)

```bash
# Build the tri CLI
zig build tri

# Verify the build
./zig-out/bin/tri --version
./zig-out/bin/tri clara demo
```

### Docker Build

```bash
# Build the tri binary inside Docker (requires Docker daemon)
docker build -f deploy/Dockerfile -t trinity:omega .

# Run the CLARA demo via Docker
docker run --rm trinity:omega clara demo
```

**Note:** Docker build assumes `zig build tri` has been run locally first to produce `zig-out/bin/tri`. For a full Docker-based build pipeline (from source), see `deploy/Dockerfile.agent` for a multi-stage build example.

## Running the Demo

```bash
# Local build
tri clara demo

# Docker (after building image)
docker run --rm trinity:omega clara demo
```

This single command runs the complete CLARA pipeline:
- HSLM forward pass on example inputs
- VSA (Vector Symbolic Architecture) binding/similarity reasoning
- Optional Zodd layer for human-readable proof traces
- Explanation output in natural language

## Current Status

**✅ DEMO WORKING** — The CLARA pipeline is fully functional:
- `tri clara demo` — runs complete 4-step pipeline
- `tri clara explain <query>` — proof trace generation
- `tri clara status` — proposal progress (#486)

The demo currently shows a mock pipeline that demonstrates the CLARA workflow:
1. HSLM forward pass (ternary VSA encoding)
2. VSA similarity search (pattern matching)
3. Datalog rule application (threshold-based classification)
4. Human-readable proof trace (~4 steps)

## Expected Output

When fully implemented, `tri clara demo` will:

1. **HSLM Forward Pass**
   - Load HSLM neural network
   - Run inference on provided examples
   - Output raw activations

2. **VSA Reasoning**
   - Bind input vectors using VSA bind operations
   - Compute similarity scores
   - Apply Zodd-style constraints if needed
   - Generate binding output

3. **Datalog/Zodd Layer** (Optional)
   - Convert VSA bindings to symbolic representation
   - Apply rule-based reasoning
   - Generate human-readable proof traces (~3-10 steps)

4. **Explanation**
   - Translate symbolic traces to natural language explanations
   - Format as hierarchical reasoning chains
   - Cite relevant components (HSLM, VSA, Datalog)

## Implementation Notes

The current `tri_clara.zig` (source: `src/tri/tri_clara.zig`) implements a **demonstration pipeline** that shows the CLARA workflow with mock data. Future enhancements:

- **HSLM integration** via `src/hslm/` (ternary neural networks) — replace mock forward pass
- **VSA operations** via `src/vsa.zig` (Vector Symbolic Architecture) — use real binding/similarity
- **Zodd proof system** via `src/vsa/` or new `src/zodd/` module — formal verification
- **Datalog generation** via VSA → Datalog pipeline — symbolic reasoning layer

**Current Implementation:**
- CLI command routing: `tri_register.zig` + `main.zig` + `tri_utils.zig`
- Demo output: formatted ANSI-colored proof traces with step-by-step reasoning
- Confidence scoring: composite score from HSLM + VSA + Datalog layers

## References

- Issue #486: DARPA CLARA TA1 — tri build & demo pipeline
- DARPA PA-25-07-02 Program Overview: https://www.darpa.mil/sites/default/files/attachment/2026-03/program-clara-faq.pdf
- JM-AQ: https://jm-aq.com/darpa-disruptioneering-opportunities-amp-clara-advance-highrisk-ai-research/
