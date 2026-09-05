# Ternary compute on an open FPGA toolchain — technical brief

One page of what exists, measured. Nothing here is projected, and the things
that are not measured are named as such.

---

## What the artifact is

A compute node that evaluates a 32-wide ternary dot product

```
y = sum_{i=0..31} w[i] * x[i],    w[i], x[i] in {-1, 0, +1}
```

on a Xilinx Artix-7 (XC7A200T), and returns the answer with a checksum that
binds it to the exact job bytes, a nonce, and the node's identity. One dot
product is one row of a ternary-weight matrix multiply, so a ternary model's
forward pass decomposes into these without remainder.

The whole flow is open: yosys plus nextpnr-xilinx (openXC7), no vendor tools.

## What is measured

| | |
|---|---|
| Correctness on the FPGA (Artix-7 XC7A200T) | 512/512 jobs, each requiring both a bit-exact result against an independent oracle and a matching receipt tag |
| Independence of the result | a second host, written in a different language with a different serial implementation, reaches the same board and agrees |
| Logic cost | 429 logic cells, 296 + 125 flip-flops, **0 DSP48** — the datapath is popcount and an adder tree, no multiplier |
| Simulation agreement | 128/128 golden vectors through the full UART frame path, gating synthesis in CI |
| Adversarial behaviour | a node that skips the work and tags its guess correctly is rejected; so are replays, identity claims and double-billing (42 tests) |

## What is not measured, and should not be inferred

- **No power figure. No TOPS/W.** Nothing in this artifact has been on a bench
  supply. Any efficiency comparison would be fabricated.
- **No multi-board result.** One board exists. Every distributed property is
  demonstrated with one physical node and software peers, and the tooling
  reports the share of each run dispatched to serial-attached nodes rather than rounding it up.
- **Throughput is transport-bound, not compute-bound.** The node speaks UART at
  160 kbaud. That is a property of the current I/O, not of the cell.
- **The receipt does not prove where the work ran.** The checksum is keyless and
  publicly computable, and the node identity is a synthesis-time constant.
  Software can produce an indistinguishable receipt. Device DNA is readable over
  JTAG, so it is an identifier, not a secret; unforgeability would need a key in
  eFUSE or BBRAM plus an encrypted bitstream.

## What this is actually good for today

Not throughput. Two things:

**1. A reproducible open-toolchain ternary baseline.** Bit-exact against an
independent oracle, gated in CI, buildable by anyone with Docker and no vendor
licence. Ternary accelerator papers are hard to compare because each carries its
own arithmetic; a cell whose every answer is checked against a golden oracle is
a fixed point to compare against.

**2. A verification discipline that survives contact with hardware.** Three
independent implementations of the same law — Verilog, Python, Zig — that CI
refuses to let diverge, and a static guard that checks every conformance host
still addresses its wrapper's operands. That guard was written because 32 hosts
had silently been feeding their cores `0 + 0` for two weeks while every
self-test passed.

## Who might have a workload for this

Listed with the reason, not as a pipeline. Each is a hypothesis to test with one
conversation.

| Candidate | Why plausibly a fit | What would have to be true |
|---|---|---|
| Teams deploying 1.58-bit / BitNet-class models at the edge | Weights are already ternary; the arithmetic maps with no quantisation loss | They have a power or latency ceiling a GPU cannot meet |
| Robotics and sensor fusion | Hard latency ceilings, hard power budgets, FPGAs already in the stack | Their model tolerates ternary weights |
| Space and radiation-tolerant compute | FPGA is already the norm; low logic cost matters; determinism is required | They need inference, not just DSP |
| Hyperdimensional computing / VSA users | The representation is *natively* ternary — no quantisation step at all | They are compute-bound rather than memory-bound |
| Academic groups publishing ternary accelerators | Need a comparable, open, bit-exact baseline | They value reproducibility over peak numbers |
| Always-on keyword spotting / TinyML | Duty-cycled, power-dominated, small models | Their model fits the logic budget |

## What a first engagement would look like

1. They name a layer shape and a weight file.
2. It is mapped to jobs and run — on the board where it fits, in software where
   it does not, with the split reported.
3. They get the measured latency, the logic cost, and an honest statement of
   what the current transport ceiling does to it.

No token, no network membership, no purchase required. The point of the first
conversation is to find out whether anyone's real workload survives contact with
these constraints.

## The honest ask

If the answer is "the numbers don't clear our bar", that is the most useful
outcome available and worth saying plainly. The engineering here is solid; what
is unknown is whether a buyer exists at this performance point, and no amount of
further engineering answers that.

---

Contact and source: <https://github.com/gHashTag/trinity-fpga>
Architecture: `docs/TRI_NET_ARCHITECTURE.md`
Evidence record: `specs/trinet/ternary_hw_verification.t27`
