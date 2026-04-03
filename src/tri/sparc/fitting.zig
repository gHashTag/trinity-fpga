//! Grid Search Fitting Engine
//! φ² + 1/φ² = 3 | TRINITY
//!
//! Implements 4D grid search optimization for fitting Savchenko
//! dark matter models to galaxy rotation curves using χ² goodness-of-fit.

const std = @import("std");
const Allocator = std.mem.Allocator;
const math = std.math;

const Savchenko = @import("savchenko.zig");
const GalaxyDataPoint = @import("mod.zig").GalaxyDataPoint;
const SavchenkoParams = @import("mod.zig").SavchenkoParams;
const FitResult = @import("mod.zig").FitResult;

/// Fitting error set
pub const FittingError = error{
    InsufficientData,
    InvalidBounds,
    SearchFailed,
};

/// Default grid search bounds for Savchenko parameters
pub const DefaultBounds = struct {
    rho0_min: f64 = 0.001,
    rho0_max: f64 = 1.0,      // M☉/pc³
    rho0_steps: usize = 20,

    r_mem_min: f64 = 1.0,
    r_mem_max: f64 = 20.0,      // kpc
    r_mem_steps: usize = 20,

    r_core_min: f64 = 0.1,
    r_core_max: f64 = 5.0,       // kpc
    r_core_steps: usize = 20,

    upsilon_bul_min: f64 = 0.1,
    upsilon_bul_max: f64 = 5.0,      // dimensionless
    upsilon_bul_steps: usize = 20,
};

/// Compute χ² for a model fit to observed data
/// χ² = Σ (V_obs - V_model)² / σ²
///
/// # Parameters
///   - allocator: Memory allocator
///   - points: Observed galaxy data
///   - params: Model parameters
///   - dr: Integration step size
///
/// # Returns
///   χ² value
pub fn computeChiSquared(
    allocator: Allocator,
    points: []const GalaxyDataPoint,
    params: SavchenkoParams,
    dr: f64,
) !f64 {
    if (points.len == 0) return error.InsufficientData;

    var chi_sq: f64 = 0;

    for (points) |point| {
        const v_model = try Savchenko.totalVelocity(
            allocator,
            point.radius,
            params.rho0,
            params.r_mem,
            params.r_core,
            point.velocity, // Assume V_obs ≈ V_disk at each radius
            0,            // No bulge contribution (or estimate separately)
            dr,
        );

        const residual = point.velocity - v_model;
        const sigma = if (point.velocity_err > 0.1) point.velocity_err else 1.0; // Minimum error floor
        const contribution = (residual * residual) / (sigma * sigma);

        chi_sq += contribution;
    }

    return chi_sq;
}

/// Find best fit using 4D grid search
///
/// # Parameters
///   - allocator: Memory allocator
///   - points: Observed galaxy data
///   - bounds: Search bounds and step counts
///   - dr: Integration step size
///
/// # Returns
///   Best fit result
pub fn gridSearchFit(
    allocator: Allocator,
    points: []const GalaxyDataPoint,
    bounds: DefaultBounds,
    dr: f64,
) !FitResult {
    if (points.len == 0) return error.InsufficientData;

    std.debug.print("Starting 4D grid search...\n", .{});
    std.debug.print("  ρ₀: {d:.3}-{d:.3} ({d} steps)\n", .{ bounds.rho0_min, bounds.rho0_max, bounds.rho0_steps });
    std.debug.print("  r_mem: {d:.3}-{d:.3} ({d} steps)\n", .{ bounds.r_mem_min, bounds.r_mem_max, bounds.r_mem_steps });
    std.debug.print("  r_core: {d:.3}-{d:.3} ({d} steps)\n", .{ bounds.r_core_min, bounds.r_core_max, bounds.r_core_steps });
    std.debug.print("  Υ_bul: {d:.3}-{d:.3} ({d} steps)\n", .{ bounds.upsilon_bul_min, bounds.upsilon_bul_max, bounds.upsilon_bul_steps });

    const total_iterations = bounds.rho0_steps * bounds.r_mem_steps *
                        bounds.r_core_steps * bounds.upsilon_bul_steps;
    std.debug.print("Total iterations: {}\n", .{total_iterations});

    // Calculate step sizes
    const rho0_step = (bounds.rho0_max - bounds.rho0_min) / @as(f64, @intFromFloat(bounds.rho0_steps - 1));
    const r_mem_step = (bounds.r_mem_max - bounds.r_mem_min) / @as(f64, @intFromFloat(bounds.r_mem_steps - 1));
    const r_core_step = (bounds.r_core_max - bounds.r_core_min) / @as(f64, @intFromFloat(bounds.r_core_steps - 1));
    const upsilon_step = (bounds.upsilon_bul_max - bounds.upsilon_bul_min) / @as(f64, @intFromFloat(bounds.upsilon_bul_steps - 1));

    var best_params: SavchenkoParams = undefined;
    var best_chi: f64 = std.math.inf(f64);

    var iteration: usize = 0;

    // 4D nested loops
    var i: usize = 0;
    while (i < bounds.rho0_steps) : (i += 1) {
        inline while (i < bounds.rho0_steps) : (i += 1) {}
        const rho0 = bounds.rho0_min + @as(f64, @floatFromInt(i)) * rho0_step;

        var j: usize = 0;
        while (j < bounds.r_mem_steps) : (j += 1) {
            const r_mem = bounds.r_mem_min + @as(f64, @floatFromInt(j)) * r_mem_step;

            var k: usize = 0;
            while (k < bounds.r_core_steps) : (k += 1) {
                const r_core = bounds.r_core_min + @as(f64, @floatFromInt(k)) * r_core_step;

                var l: usize = 0;
                while (l < bounds.upsilon_bul_steps) : (l += 1) {
                    const upsilon = bounds.upsilon_bul_min + @as(f64, @floatFromInt(l)) * upsilon_step;

                    const params = SavchenkoParams{
                        .rho0 = rho0,
                        .r_mem = r_mem,
                        .r_core = r_core,
                        .upsilon_bul = upsilon,
                    };

                    const chi_sq = computeChiSquared(allocator, points, params, dr) catch {
                        // Skip invalid parameter combinations
                        iteration += 1;
                        continue :rho0_loop;
                    };

                    if (chi_sq < best_chi) {
                        best_chi = chi_sq;
                        best_params = params;
                    }

                    iteration += 1;

                    // Progress every 10%
                    if (iteration * 10 >= total_iterations) {
                        const progress = iteration * 100 / total_iterations;
                        std.debug.print("Progress: {}%\r", .{progress});
                    }
                }
            }
        }
    }

    std.debug.print("\n", .{}); // Newline after progress

    const dof = points.len - 4; // 4 parameters fitted
    const reduced_chi = if (dof > 0) best_chi / @as(f64, @floatFromInt(dof)) else best_chi;

    return FitResult{
        .params = best_params,
        .chi_squared = best_chi,
        .dof = dof,
        .reduced_chi_squared = reduced_chi,
    };
}

/// Fit a single galaxy with default grid search
///
/// # Parameters
///   - allocator: Memory allocator
///   - points: Observed galaxy data
///
/// # Returns
///   Best fit result
pub fn fitGalaxy(allocator: Allocator, points: []const GalaxyDataPoint) !FitResult {
    return gridSearchFit(allocator, points, DefaultBounds{}, Savchenko.DEFAULT_DR);
}

/// Check if fit meets quality criteria
///
/// # Parameters
///   - result: Fit result to evaluate
///
/// # Returns
///   true if reduced χ² < 2.0 (good fit threshold)
pub fn isGoodFit(result: FitResult) bool {
    return result.reduced_chi_squared < 2.0;
}

test "computeChiSquared for perfect fit" {
    const allocator = std.testing.allocator;
    var points = [_]GalaxyDataPoint{
        .{ .radius = 1.0, .velocity = 100.0, .velocity_err = 5.0 },
        .{ .radius = 2.0, .velocity = 110.0, .velocity_err = 5.0 },
        .{ .radius = 5.0, .velocity = 120.0, .velocity_err = 5.0 },
    };

    // Parameters that roughly match this data
    const params = SavchenkoParams{
        .rho0 = 0.05,
        .r_mem = 5.0,
        .r_core = 1.0,
        .upsilon_bul = 1.0,
    };

    const chi_sq = computeChiSquared(allocator, &points, params, 0.1) catch unreachable;

    // χ² should be positive finite value
    try std.testing.expect(std.math.isFinite(chi_sq) and chi_sq > 0);
}

test "isGoodFit classification" {
    const good_result = FitResult{
        .params = undefined,
        .chi_squared = 100.0,
        .dof = 100,
        .reduced_chi_squared = 1.0, // 100/100 < 2.0
    };

    const bad_result = FitResult{
        .params = undefined,
        .chi_squared = 100.0,
        .dof = 40,
        .reduced_chi_squared = 2.5, // 100/40 > 2.0
    };

    try std.testing.expect(isGoodFit(good_result) == true);
    try std.testing.expect(isGoodFit(bad_result) == false);
}
