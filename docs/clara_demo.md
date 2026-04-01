# CLARA Demo Documentation

## Overview

CLARA TA1 (DARPA PA-25-07-02) aims to demonstrate Trinity's compositional learning and reasoning capabilities through a clean, reproducible pipeline.

## Running the Demo

```bash
tri clara demo
```

This single command runs the complete CLARA pipeline:
- HSLM forward pass on example inputs
- VSA (Vector Symbolic Architecture) binding/similarity reasoning
- Optional Zodd layer for human-readable proof traces
- Explanation output in natural language

## Current Status

The CLARA commands are registered in `tri_register.zig` and the basic command infrastructure is in place. The `demo` subcommand currently shows:

```
TODO: Implement HSLM → VSA → Datalog → explanation pipeline
```

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

The current `tri_clara.zig` (source: `src/tri/tri_clara.zig`) is a **stub implementation** showing the command structure and TODO markers. Full implementation requires:

- HSLM integration via `src/hslm/` (ternary neural networks)
- VSA operations via `src/vsa.zig` (Vector Symbolic Architecture)
- Zodd proof system via `src/vsa/` or new `src/zodd/` module
- Datalog generation via VSA → Datalog pipeline

## References

- Issue #486: DARPA CLARA TA1 — tri build & demo pipeline
- DARPA PA-25-07-02 Program Overview: https://www.darpa.mil/sites/default/files/attachment/2026-03/program-clara-faq.pdf
- JM-AQ: https://jm-aq.com/darpa-disruptioneering-opportunities-amp-clara-advance-highrisk-ai-research/
