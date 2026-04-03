//! Savchenko Memory Density Formula
//! φ² + 1/φ² = 3 | TRINITY
//!
//! Implements the Savchenko memory density model for dark matter:
//! ρ_mem(r) = ρ₀ · exp(-r/r_mem) · (1 + ln(1 + r/r_core))
//!
//! Includes Simpson's rule integration for mass calculation and
//! circular velocity computation.

const std = @import("std");
const math = std.math;

/// Gravitational constant in (km/s)² kpc / M☉
/// G = 6.674×10⁻¹¹ m³/kg/s² ≈ 4.3009×10⁻⁶ (km/s)² kpc/M☉
pub const G_KM_KPC_SOLAR: f64 = 4.3009e-6;

/// Integration step size in kpc (default for Simpson's rule)
pub const DEFAULT_DR: f64 = 0.01;

/// Maximum radius for integration in kpc
pub const MAX_R_KPC: f64 = 100.0;

/// Savchenko memory density at radius r
/// ρ_mem(r) = ρ₀ · exp(-r/r_mem) · (1 + ln(1 + r/r_core))
///
/// # Parameters
///   - r: Radius in kpc
///   - rho0: Central density in M☉/pc³
///   - r_mem: Memory radius in kpc
///   - r_core: Core radius in kpc
///
/// # Returns
///   Density in M☉/pc³
pub fn savchenkoDensity(r: f64, rho0: f64, r_mem: f64, r_core: f64) f64 {
    if (r < 0) return rho0; // At center, use central density
    if (r_mem <= 0 or r_core <= 0) return 0;

    const x = r / r_mem;
    const y = r / r_core;
    const exp_term = @exp(-x);
    const log_term = 1 + math.log1p(y);

    return rho0 * exp_term * log_term;
}

/// Enclosed mass within radius r using Simpson's rule
/// M(r) = 4π ∫₀ʳ ρ(r') r'² dr'
///
/// # Parameters
///   - allocator: Memory allocator for temporary arrays
///   - r: Radius in kpc
///   - rho0: Central density in M☉/pc³
///   - r_mem: Memory radius in kpc
///   - r_core: Core radius in kpc
///   - dr: Integration step size in kpc (default: 0.01)
///
/// # Returns
///   Enclosed mass in M☉
pub fn enclosedMass(
    r: f64,
    rho0: f64,
    r_mem: f64,
    r_core: f64,
    dr: f64,
) !f64 {
    if (r <= 0) return 0;
    if (dr <= 0) return error.InvalidStepSize;

    const n = @as(usize, @intFromFloat(@ceil(r / dr)));
    if (n % 2 != 0) return error.EvenNumberOfIntervalsRequired;

    // Simpson's rule: M = 4π ∫ ρ(r) r² dr
    // Convert density from M☉/pc³ to M☉/kpc³: multiply by 10⁹
    const pc3_to_kpc3: f64 = 1e9;

    var integral: f64 = 0;
    var i: usize = 0;
    while (i <= n) : (i += 1) {
        const r_i = @as(f64, @floatFromInt(i)) * dr;
        if (r_i > r) break;

        const rho = savchenkoDensity(r_i, rho0, r_mem, r_core);
        const integrand = rho * r_i * r_i * pc3_to_kpc3;

        var coeff: f64 = 2.0; // Simpson's rule: middle points get coefficient 4, ends get 1
        if (i == 0 or i == n) {
            coeff = 1.0;
        } else if (i % 2 == 1) {
            coeff = 4.0;
        }
        integral += coeff * integrand;
    }

    // Simpson's rule: (dr/3) × sum
    // Factor: 4π for spherical symmetry
    return (dr / 3.0) * integral * 4.0 * math.pi;
}

/// Dark matter circular velocity at radius r
/// V_DM²(r) = GM(r) / r
///
/// # Parameters
///   - allocator: Memory allocator
///   - r: Radius in kpc
///   - rho0: Central density in M☉/pc³
///   - r_mem: Memory radius in kpc
///   - r_core: Core radius in kpc
///   - dr: Integration step size
///
/// # Returns
///   Circular velocity in km/s
pub fn darkMatterVelocity(
    r: f64,
    rho0: f64,
    r_mem: f64,
    r_core: f64,
    dr: f64,
) !f64 {
    if (r <= 0) return 0;

    const mass = try enclosedMass(r, rho0, r_mem, r_core, dr);
    const v_squared = G_KM_KPC_SOLAR * mass / r;

    return @sqrt(@max(0, v_squared));
}

/// Compute total velocity at radius r (including disk and bulge contributions)
/// V_total² = V_DM² + V_disk² + V_bulge²
///
/// # Parameters
///   - allocator: Memory allocator
///   - r: Radius in kpc
///   - rho0: Central density in M☉/pc³
///   - r_mem: Memory radius in kpc
///   - r_core: Core radius in kpc
///   - v_disk: Disk velocity at r (km/s)
///   - v_bulge: Bulge velocity at r (km/s)
///   - dr: Integration step size
///
/// # Returns
///   Total circular velocity in km/s
pub fn totalVelocity(
    r: f64,
    rho0: f64,
    r_mem: f64,
    r_core: f64,
    v_disk: f64,
    v_bulge: f64,
    dr: f64,
) !f64 {
    const v_dm = try darkMatterVelocity(r, rho0, r_mem, r_core, dr);
    const v_squared = v_dm * v_dm + v_disk * v_disk + v_bulge * v_bulge;

    // Compute sqrt of non-negative value
    return @sqrt(v_squared);
}

test "savchenkoDensity at zero radius" {
    const rho0: f64 = 1.0;
    const r_mem: f64 = 5.0;
    const r_core: f64 = 1.0;

    const rho = savchenkoDensity(0, rho0, r_mem, r_core);
    try std.testing.expectApproxEqAbs(rho0, rho, 1e-10);
}

test "savchenkoDensity produces reasonable values" {
    const rho0: f64 = 1.0;
    const r_mem: f64 = 5.0;
    const r_core: f64 = 1.0;

    const rho0_calc = savchenkoDensity(0, rho0, r_mem, r_core);
    const rho1 = savchenkoDensity(1, rho0, r_mem, r_core);
    const rho5 = savchenkoDensity(5, rho0, r_mem, r_core);
    const rho10 = savchenkoDensity(10, rho0, r_mem, r_core);

    // Density should be positive and finite
    try std.testing.expect(rho0_calc > 0 and rho0_calc < 2);
    try std.testing.expect(rho1 > 0 and rho1 < 2);
    try std.testing.expect(rho5 > 0 and rho5 < 2);
    try std.testing.expect(rho10 > 0 and rho10 < 2);
}

test "enclosedMass increases with radius" {
    const rho0: f64 = 0.1; // M☉/pc³
    const r_mem: f64 = 5.0; // kpc
    const r_core: f64 = 1.0; // kpc
    const dr: f64 = 0.1;

    const m1 = try enclosedMass(1.0, rho0, r_mem, r_core, dr);
    const m5 = try enclosedMass(5.0, rho0, r_mem, r_core, dr);
    const m10 = try enclosedMass(10.0, rho0, r_mem, r_core, dr);

    try std.testing.expect(m5 > m1);
    try std.testing.expect(m10 > m5);
}

test "darkMatterVelocity produces reasonable values" {
    const rho0: f64 = 0.05; // M☉/pc³
    const r_mem: f64 = 8.0; // kpc
    const r_core: f64 = 2.0; // kpc
    const dr: f64 = 0.1;

    const v5 = try darkMatterVelocity(5.0, rho0, r_mem, r_core, dr);
    const v10 = try darkMatterVelocity(10.0, rho0, r_mem, r_core, dr);

    // Velocities should be positive and in reasonable range (10-300 km/s)
    try std.testing.expect(v5 > 0 and v5 < 500);
    try std.testing.expect(v10 > 0 and v10 < 500);

    // For typical galaxy, velocity curve should be fairly flat or declining
    // V(10) should not be dramatically different from V(5) for these parameters
    const ratio = v10 / v5;
    try std.testing.expect(ratio > 0.5 and ratio < 2.0);
}
