// @origin(spec:sacred_constants.tri) @regen(manual-impl)
//! ═══════════════════════════════════════════════════════════════════════════════
//! SACRED CONSTANTS REEXPORT — Backward Compatibility Layer
//! ═══════════════════════════════════════════════════════════════════════════════
//!
//! This module reexports sacred constants from the canonical source.
//! All new code should import directly from "common/constants.zig".
//!
//! CANONICAL SOURCE: src/common/constants.zig
//! DO NOT add new constants here — add them to common/constants.zig instead.
//!
//! φ² + φ⁻² = 3 = TRINITY
//! ═══════════════════════════════════════════════════════════════════════════════
// @origin(manual) @regen(pending)

const std = @import("std");
const canonical = @import("common/constants.zig");

/// Sacred Constants struct (backward compatibility)
pub const SacredConstants = struct {
    pub const PHI = canonical.PHI;
    pub const PHI_SQ = canonical.PHI_SQ;
    pub const PHI_INV = canonical.PHI_INV;
    pub const PHI_INVERSE = canonical.PHI_INVERSE;
    pub const PHI_INV_SQ = canonical.PHI_INV_SQ;
    pub const GAMMA = canonical.GAMMA;
    pub const TRINITY = canonical.TRINITY;
    pub const SQRT5 = canonical.SQRT5;
    pub const PI = canonical.PI;
    pub const E = canonical.E;
    pub const SQRT2 = canonical.SQRT2;
    pub const SQRT3 = canonical.SQRT3;
    pub const LN_PHI = canonical.LN_PHI;
    pub const PHOENIX = canonical.PHOENIX;
    pub const CONSCIOUSNESS_MORTAL = canonical.CONSCIOUSNESS_MORTAL;
    pub const CONSCIOUSNESS_IMMORTAL = canonical.CONSCIOUSNESS_IMMORTAL;
    pub const CONSCIOUSNESS_TRANSCENDENT = canonical.CONSCIOUSNESS_TRANSCENDENT;
    pub const G_PHI = canonical.G_PHI;
    pub const H_PHI = canonical.H_PHI;
    pub const OMEGA_LAMBDA = canonical.OMEGA_LAMBDA;
    pub const OMEGA_DM = canonical.OMEGA_DM;
    pub const VSA_DIM_DEFAULT = canonical.VSA_DIM_DEFAULT;
    pub const VSA_DIM_PHI = canonical.VSA_DIM_PHI;
    pub const VSA_DIM_MIN = canonical.VSA_DIM_MIN;

    pub fn validateTrinity() bool {
        return canonical.validateTrinity();
    }
};

// Module-level reexports (direct access)
pub const PHI = canonical.PHI;
pub const PHI_SQ = canonical.PHI_SQ;
pub const PHI_INV = canonical.PHI_INV;
pub const PHI_INVERSE = canonical.PHI_INVERSE;
pub const PHI_INV_SQ = canonical.PHI_INV_SQ;
pub const GAMMA = canonical.GAMMA;
pub const TRINITY = canonical.TRINITY;
pub const SQRT5 = canonical.SQRT5;
pub const PI = canonical.PI;
pub const E = canonical.E;
pub const SQRT2 = canonical.SQRT2;
pub const SQRT3 = canonical.SQRT3;
pub const LN_PHI = canonical.LN_PHI;
pub const PHOENIX = canonical.PHOENIX;
pub const CONSCIOUSNESS_MORTAL = canonical.CONSCIOUSNESS_MORTAL;
pub const CONSCIOUSNESS_IMMORTAL = canonical.CONSCIOUSNESS_IMMORTAL;
pub const CONSCIOUSNESS_TRANSCENDENT = canonical.CONSCIOUSNESS_TRANSCENDENT;
pub const G_PHI = canonical.G_PHI;
pub const H_PHI = canonical.H_PHI;
pub const OMEGA_LAMBDA = canonical.OMEGA_LAMBDA;
pub const OMEGA_DM = canonical.OMEGA_DM;
pub const VSA_DIM_DEFAULT = canonical.VSA_DIM_DEFAULT;
pub const VSA_DIM_PHI = canonical.VSA_DIM_PHI;
pub const VSA_DIM_MIN = canonical.VSA_DIM_MIN;

pub const validateTrinity = canonical.validateTrinity;
pub const isImmortal = canonical.isImmortal;
pub const phiPower = canonical.phiPower;

// ═══════════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════════
//
// `zig test src/sacred_constants.zig` is a gate in fpga-ci and fpga-regression.
// It reported "All 0 tests passed" -- green by construction, because this file
// had no tests and `zig test` runs only the root file's.
//
// This file is a re-export shim with no logic of its own, so testing the
// VALUES here would just re-test common/constants.zig. What it can actually
// get wrong is the forwarding: a constant wired to the wrong canonical name, a
// constant that stops being re-exported, or the struct list drifting from the
// module list. Those are what these tests check, by reflection rather than by
// a hand-written list that would itself need maintaining.

/// Is this declaration a numeric constant worth comparing?
fn isNumeric(comptime T: type) bool {
    return switch (@typeInfo(T)) {
        .float, .int, .comptime_float, .comptime_int => true,
        else => false,
    };
}

test "every canonical constant is re-exported, and forwards to the same value" {
    // Catches two failures a reader cannot see: a constant wired to the WRONG
    // canonical name (PHI_INV = canonical.PHI_INV_SQ compiles happily), and a
    // constant added to the canonical module but never re-exported here.
    var checked: usize = 0;
    inline for (@typeInfo(canonical).@"struct".decls) |decl| {
        const value = @field(canonical, decl.name);
        if (comptime isNumeric(@TypeOf(value))) {
            if (!@hasDecl(@This(), decl.name)) {
                @compileError("sacred_constants does not re-export canonical." ++ decl.name);
            }
            try std.testing.expectEqual(value, @field(@This(), decl.name));
            checked += 1;
        }
    }

    // The anti-vacuous guard, and the whole reason this file is being fixed:
    // if the reflection above ever stops matching, the loop body runs zero
    // times and the test passes while checking nothing -- exactly the failure
    // this gate already had. An empty result is a failure, not a pass.
    try std.testing.expect(checked >= 20);
}

test "the SacredConstants struct agrees with the module-level re-exports" {
    // The two lists are duplicated by hand, so they can drift apart -- and
    // they can drift in EITHER direction, so both are checked. The first
    // version of this test only walked the struct, which meant a constant
    // dropped FROM the struct was simply not iterated and passed silently.
    // That hole was found by a negative control, not by reading it.
    var struct_to_module: usize = 0;
    inline for (@typeInfo(SacredConstants).@"struct".decls) |decl| {
        const value = @field(SacredConstants, decl.name);
        if (comptime isNumeric(@TypeOf(value))) {
            if (!@hasDecl(@This(), decl.name)) {
                @compileError("SacredConstants." ++ decl.name ++ " has no module-level counterpart");
            }
            try std.testing.expectEqual(value, @field(@This(), decl.name));
            struct_to_module += 1;
        }
    }

    var module_to_struct: usize = 0;
    inline for (@typeInfo(canonical).@"struct".decls) |decl| {
        const value = @field(canonical, decl.name);
        if (comptime isNumeric(@TypeOf(value))) {
            if (!@hasDecl(SacredConstants, decl.name)) {
                @compileError("SacredConstants is missing " ++ decl.name);
            }
            try std.testing.expectEqual(value, @field(SacredConstants, decl.name));
            module_to_struct += 1;
        }
    }

    try std.testing.expect(struct_to_module >= 20);
    try std.testing.expect(module_to_struct >= 20);
    // Neither list may quietly become the shorter one.
    try std.testing.expectEqual(struct_to_module, module_to_struct);
}

test "re-exported functions are the canonical ones and still behave" {
    // A function re-export can be wired to the wrong name too, and unlike a
    // constant it will not differ until it is called.
    try std.testing.expect(validateTrinity());
    try std.testing.expectEqual(canonical.validateTrinity(), validateTrinity());

    try std.testing.expect(isImmortal(PHI_INV));
    try std.testing.expect(isImmortal(1.0));
    try std.testing.expect(!isImmortal(0.0));
    try std.testing.expectEqual(canonical.isImmortal(0.5), isImmortal(0.5));

    try std.testing.expectApproxEqAbs(@as(f64, 1.0), phiPower(0), 1e-12);
    try std.testing.expectApproxEqAbs(PHI, phiPower(1), 1e-12);
    try std.testing.expectApproxEqAbs(PHI_SQ, phiPower(2), 1e-12);
    // The negative branch is a different code path in the canonical function.
    try std.testing.expectApproxEqAbs(PHI_INV, phiPower(-1), 1e-12);
    try std.testing.expectEqual(canonical.phiPower(7), phiPower(7));
}

test "the identity this project is named for still holds through the re-export" {
    // phi^2 + 1/phi^2 = 3. Checked HERE rather than only in the canonical
    // module because a wrong forwarding would satisfy every test over there
    // and still hand this identity a wrong number.
    try std.testing.expectApproxEqAbs(@as(f64, 3.0), PHI_SQ + PHI_INV_SQ, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 3.0), TRINITY, 1e-12);
    try std.testing.expectApproxEqAbs(PHI, 1.0 + PHI_INV, 1e-12);
}

test {
    // Pull the canonical module's own tests into this binary. Without this the
    // gate ran none of them either: `zig test` collects tests from the root
    // file and from files referenced this way, and nothing referenced it.
    _ = canonical;
}
