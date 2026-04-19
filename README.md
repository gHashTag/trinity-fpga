
## Architecture

Trinity is an orchestrator connecting a family of focused micro-repositories. Each repo has a single responsibility and can be used independently.

### Dependency Graph

```
zig-golden-float          ← Numerical core (GF16, TF3, JIT, VM)
         ↑
zig-sacred-geometry     ← φ, Sacred geometry (~58KB)
zig-physics             ← Quantum physics, QCD, gravity (~36KB)
zig-hdc                 ← Hyperdimensional Computing (~352KB)
zig-knowledge-graph     ← KG server + CLI (~100KB)
trinity-training        ← HSLM, benchmarks, datasets (208MB data)
         ↑
zig-agents              ← Agents, MCP, autonomous (~519KB)
zig-crypto-mining       ← BTC mining MVP, DePIN (~60KB)
         ↑
trinity                 ← Orchestrator (links all repos via build.zig.zon)
```

### Using a Module Independently

Each micro-repo is a standalone Zig package:

```zig
// build.zig.zon
.dependencies = .{
    .zig_golden_float = .{
        .url = "https://github.com/gHashTag/zig-golden-float/archive/main.tar.gz",
        .hash = "...", // run `zig fetch --save` to get hash
    },
},
```

```bash
zig fetch --save https://github.com/gHashTag/zig-golden-float/archive/main.tar.gz
```

