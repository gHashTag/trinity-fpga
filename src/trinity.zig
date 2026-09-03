// @origin(spec:trinity.tri) @regen(manual-impl)
// @origin(manual) @regen(pending)
// 🤖 TRINITY v1.0.1 "ASCENSION": Official Production Release
// Trinity - Ternary Vector Symbolic Architecture
// High-performance hyperdimensional computing library
//
// ⲤⲀⲔⲢⲀ ⲪⲞⲢⲘⲨⲖⲀ: V = n × 3^k × π^m × φ^p × e^q
// φ² + 1/φ² = 3

const std = @import("std");

// Core modules
pub const bigint = @import("vsa_hybrid/bigint.zig");
pub const packed_trit = @import("vsa_hybrid/packed_trit.zig");
pub const hybrid = @import("vsa_hybrid/hybrid.zig");
// src/vsa/ was extracted to gHashTag/zig-hdc and this directory is now empty;
// the module `vsa` is that package's `zig-hdc-vsa`, whose root is the very
// src/vsa.zig that used to live here. So `core` comes back through it.
pub const vsa = @import("vsa").core;

// vsa_agent is NOT restored. zig-hdc declines to export vsa/agent.zig with a
// note that it "cannot compile and never could": it is a facade over
// agent/types.zig, memory.zig, unified.zig, autonomous.zig and system.zig,
// five files absent from that package and from gHashTag/trinity, which is
// where it was migrated from. Verified here rather than taken on trust --
// all five are absent.
//
// Re-exporting it from this root made every consumer of `trinity` unbuildable
// for the sake of a name that resolves to nothing. Whether the agent layer
// gets finished or dropped is a decision about that library, not a way to turn
// this build green -- which is the same reason zig-hdc left the file in place
// and merely stopped exporting it.
pub const vm = @import("vm.zig");

// SDK modules (high-level API)
pub const sdk = @import("sdk.zig");
pub const science = @import("science.zig");
pub const sparse = @import("sparse.zig");
pub const jit = @import("jit.zig");

// Re-export main types.
//
// HybridBigInt and Trit come from the MODULE, not from src/vsa_hybrid/. That
// directory is a local leftover of the same types the `vsa` module exports,
// and taking the type from one while taking bind/bundle/permute from the other
// splits one structural type into two nominal ones -- which is every
// "expected vsa_hybrid.hybrid_impl.HybridBigInt, found ternary.hybrid.HybridBigInt"
// that consumers of this root were failing on.
const vsa_mod = @import("vsa");
pub const BigInt = bigint.TVCBigInt;
pub const PackedBigInt = packed_trit.PackedBigInt;
pub const HybridBigInt = vsa_mod.HybridBigInt;
pub const Trit = vsa_mod.Trit;

// Re-export VSA operations
pub const bind = vsa.bind;
pub const unbind = vsa.unbind;
pub const bundle2 = vsa.bundle2;
pub const bundle3 = vsa.bundle3;
pub const cosineSimilarity = vsa.cosineSimilarity;
pub const hammingDistance = vsa.hammingDistance;
pub const hammingSimilarity = vsa.hammingSimilarity;
pub const dotSimilarity = vsa.dotSimilarity;
pub const permute = vsa.permute;
pub const inversePermute = vsa.inversePermute;
pub const encodeSequence = vsa.encodeSequence;
pub const probeSequence = vsa.probeSequence;
pub const randomVector = vsa.randomVector;
pub const bundleN = vsa.bundleN;
pub const countNonZero = vsa.countNonZero;
pub const vectorNorm = vsa.vectorNorm;

// Re-export VM
pub const VSAVM = vm.VSAVM;
pub const VSAInstruction = vm.VSAInstruction;
pub const VSAOpcode = vm.VSAOpcode;

// Re-export SDK types (for developers)
pub const Hypervector = sdk.Hypervector;
pub const Codebook = sdk.Codebook;
pub const AssociativeMemory = sdk.AssociativeMemory;
pub const SequenceEncoder = sdk.SequenceEncoder;
pub const GraphEncoder = sdk.GraphEncoder;
pub const Classifier = sdk.Classifier;

// Re-export Science types (for researchers)
pub const VectorStats = science.VectorStats;
pub const DistanceMetric = science.DistanceMetric;
pub const ResonatorNetwork = science.ResonatorNetwork;
pub const computeStats = science.computeStats;
pub const distance = science.distance;
pub const mutualInformation = science.mutualInformation;
pub const batchSimilarity = science.batchSimilarity;
pub const batchBundle = science.batchBundle;
pub const weightedBundle = science.weightedBundle;

// Re-export Sparse types
pub const SparseVector = sparse.SparseVector;

// Re-export JIT types
pub const JitCompiler = jit.JitCompiler;
pub const JitCache = jit.JitCache;

// Constants
pub const MAX_TRITS = vsa_mod.MAX_TRITS;
// TRITS_PER_BYTE is not exported from the module root, so it stays local --
// and it lives in packed_trit, not hybrid, which is where I first pointed it.
pub const TRITS_PER_BYTE = packed_trit.TRITS_PER_BYTE;
pub const PHI = science.PHI;
pub const PHI_SQUARED = science.PHI_SQUARED;
pub const GOLDEN_IDENTITY = science.GOLDEN_IDENTITY;

// Version
pub const version = "1.0.1";

test {
    // Run all tests from submodules
    std.testing.refAllDecls(@This());
}

// φ² + 1/φ² = 3 | TRINITY
