//! SPARC (Spitzer Photometry and Accurate Rotation Curves) Module
//! φ² + 1/φ² = 3 | TRINITY
//!
//! Fits Savchenko memory density models to galaxy rotation curves using
//! grid search optimization with χ² goodness-of-fit metric.
//!
//! # Features
//! - Download and parse SPARC data from astroweb.case.edu
//! - Savchenko memory density formula implementation
//! - Simpson's rule numerical integration
//! - 4D grid search (ρ₀, r_mem, r_core, Υ_bul)
//! - Multiple output formats: ANSI text, JSON, CSV

const std = @import("std");
const Allocator = std.mem.Allocator;

pub const Savchenko = @import("savchenko.zig");
pub const Data = @import("data.zig");
pub const Fitting = @import("fitting.zig");
pub const Embeds = @import("embeds.zig");

const Cli = @import("cli.zig");

/// SPARC galaxy data point
pub const GalaxyDataPoint = struct {
    radius: f64, // kpc
    velocity: f64, // km/s
    velocity_err: f64, // km/s
};

/// SPARC galaxy dataset
pub const GalaxyDataset = struct {
    name: []const u8,
    points: []GalaxyDataPoint,
    distance: f64, // Mpc
    inclination: f64, // degrees
    position_angle: f64, // degrees

    pub fn deinit(self: *GalaxyDataset, allocator: Allocator) void {
        allocator.free(self.name);
        allocator.free(self.points);
    }
};

/// Savchenko model parameters
pub const SavchenkoParams = struct {
    rho0: f64, // Central density (M☉/pc³)
    r_mem: f64, // Memory radius (kpc)
    r_core: f64, // Core radius (kpc)
    upsilon_bul: f64, // Baryon mass-to-light ratio
};

/// Fit result with χ² value
pub const FitResult = struct {
    params: SavchenkoParams,
    chi_squared: f64,
    dof: usize, // Degrees of freedom
    reduced_chi_squared: f64,
};

pub fn runCommand(allocator: Allocator, args: []const []const u8) !void {
    try Cli.run(allocator, args);
}
