//! SPARC CLI Command Handler
//! φ² + 1/φ² = 3 | TRINITY
//!
//! Command-line interface for `tri sparc fit` and `tri sparc plot`.
//! Supports multiple output formats: ANSI text, JSON, CSV.

const std = @import("std");
const Allocator = std.mem.Allocator;
const json = std.json;

const Data = @import("data.zig");
const Fitting = @import("fitting.zig");
const mod = @import("mod.zig");
const Savchenko = @import("savchenko.zig");

/// ANSI color codes for terminal output
const Color = enum {
    reset,
    red,
    green,
    yellow,
    blue,
    cyan,
    magenta,
};

const ColorCode = struct {
    red: []const u8 = "\x1b[31m",
    green: []const u8 = "\x1b[32m",
    yellow: []const u8 = "\x1b[33m",
    blue: []const u8 = "\x1b[34m",
    cyan: []const u8 = "\x1b[36m",
    magenta: []const u8 = "\x1b[35m",
    reset: []const u8 = "\x1b[0m",
};

fn colorize(s: []const u8, color: Color) []const u8 {
    return switch (color) {
        .red => ColorCode.red ++ s ++ ColorCode.reset,
        .green => ColorCode.green ++ s ++ ColorCode.reset,
        .yellow => ColorCode.yellow ++ s ++ ColorCode.reset,
        .blue => ColorCode.blue ++ s ++ ColorCode.reset,
        .cyan => ColorCode.cyan ++ s ++ ColorCode.reset,
        .magenta => ColorCode.magenta ++ s ++ ColorCode.reset,
        .reset => ColorCode.reset ++ s,
    };
}

/// Output format options
pub const OutputFormat = enum {
    text, // ANSI colored terminal output
    json, // Structured JSON
    csv, // Comma-separated values
};

/// SPARC command options
pub const SparcOptions = struct {
    command: Command = .fit,
    galaxy_name: []const u8 = "",
    format: OutputFormat = .text,
    profile: ProfileType = .savchenko,
    use_cache: bool = true,
    dr: f64 = Savchenko.DEFAULT_DR,
    verbose: bool = false,
};

pub const Command = enum {
    fit,
    plot,
    list,
};

pub const ProfileType = enum {
    savchenko,
    nfw,
};

/// Parse command-line arguments for SPARC commands
///
/// # Parameters
///   - allocator: Memory allocator
///   - args: Command-line arguments (excluding "sparc")
///
/// # Returns
///   Parsed options
pub fn parseArgs(allocator: Allocator, args: []const []const u8) !SparcOptions {
    var options = SparcOptions{};

    if (args.len == 0) {
        return error.NoCommand;
    }

    // Parse subcommand
    const cmd_str = args[0];
    if (std.mem.eql(u8, cmd_str, "fit")) {
        options.command = .fit;
    } else if (std.mem.eql(u8, cmd_str, "plot")) {
        options.command = .plot;
    } else if (std.mem.eql(u8, cmd_str, "list")) {
        options.command = .list;
    } else {
        std.debug.print("Unknown command: {s}\n", .{cmd_str});
        return error.UnknownCommand;
    }

    // Parse remaining arguments
    var i: usize = 1;
    while (i < args.len) : (i += 1) {
        const arg = args[i];

        if (std.mem.eql(u8, arg, "--help") or std.mem.eql(u8, arg, "-h")) {
            printUsage(allocator);
            std.process.exit(0);
        } else if (std.mem.eql(u8, arg, "--format") or std.mem.eql(u8, arg, "-f")) {
            if (i + 1 >= args.len) return error.MissingFormatValue;
            i += 1;
            const fmt = args[i];
            if (std.mem.eql(u8, fmt, "json")) {
                options.format = .json;
            } else if (std.mem.eql(u8, fmt, "csv")) {
                options.format = .csv;
            } else if (std.mem.eql(u8, fmt, "text")) {
                options.format = .text;
            } else {
                return error.UnknownFormat;
            }
        } else if (std.mem.eql(u8, arg, "--profile") or std.mem.eql(u8, arg, "-p")) {
            if (i + 1 >= args.len) return error.MissingProfileValue;
            i += 1;
            const prof = args[i];
            if (std.mem.eql(u8, prof, "nfw")) {
                options.profile = .nfw;
            } else if (std.mem.eql(u8, prof, "savchenko")) {
                options.profile = .savchenko;
            } else {
                return error.UnknownProfile;
            }
        } else if (std.mem.eql(u8, arg, "--no-cache")) {
            options.use_cache = false;
        } else if (std.mem.eql(u8, arg, "--dr")) {
            if (i + 1 >= args.len) return error.MissingDrValue;
            i += 1;
            options.dr = try std.fmt.parseFloat(f64, args[i]);
            if (options.dr <= 0 or options.dr > 1.0) return error.InvalidDrValue;
        } else if (std.mem.eql(u8, arg, "--verbose") or std.mem.eql(u8, arg, "-v")) {
            options.verbose = true;
        } else if (arg[0] != '-') {
            // Positional argument = galaxy name
            if (options.galaxy_name.len > 0) return error.MultipleGalaxyNames;
            options.galaxy_name = arg;
        }
    }

    return options;
}

/// Print usage information
fn printUsage(allocator: Allocator) void {
    const stdout = std.io.getStdOut().writer();
    _ = allocator; // autofix

    stdout.print(
        \\SPARC (Spitzer Photometry and Accurate Rotation Curves) Analysis
        \\
        \\Usage: tri sparc <command> [options] [galaxy]
        \\
        \\Commands:
        \\  fit    Fit Savchenko model to galaxy rotation curve
        \\  plot   Plot rotation curve (ASCII)
        \\  list    List available galaxies
        \\
        \\Fit Options:
        \\  -f, --format <fmt>    Output format: text, json, csv (default: text)
        \\  -p, --profile <type>   Density profile: savchenko, nfw (default: savchenko)
        \\  --no-cache             Force download, skip cache
        \\  --dr <value>           Integration step size in kpc (default: 0.01)
        \\  -v, --verbose           Show detailed progress
        \\  -h, --help              Show this help
        \\
        \\Examples:
        \\  tri sparc fit NGC2403
        \\  tri sparc fit UGC1234 --format json
        \\  tri sparc fit IC342 --dr 0.05 --verbose
        \\  tri sparc list
    , .{}) catch unreachable;
}

/// Run SPARC command based on parsed options
///
/// # Parameters
///   - allocator: Memory allocator
///   - options: Parsed command options
pub fn run(allocator: Allocator, options: SparcOptions) !void {
    switch (options.command) {
        .fit => try runFit(allocator, options),
        .plot => try runPlot(allocator, options),
        .list => try runList(allocator, options),
    }
}

/// Run fit command
fn runFit(allocator: Allocator, options: SparcOptions) !void {
    // Download or load data
    const data_content = try Data.downloadSPARCData(allocator, options.use_cache);
    defer allocator.free(data_content);

    const points = try Data.parseSPARCData(allocator, data_content);
    defer allocator.free(points);

    if (points.len == 0) {
        std.debug.print("No valid data points found.\n", .{});
        return error.NoData;
    }

    std.debug.print("Loaded {} data points\n", .{points.len});

    // Run fitting
    const result = try Fitting.fitGalaxy(allocator, points);

    // Output based on format
    switch (options.format) {
        .text => try outputText(allocator, result, options),
        .json => try outputJson(allocator, result, points),
        .csv => try outputCsv(allocator, result, points),
    }
}

/// Output fit results in ANSI text format
fn outputText(allocator: Allocator, result: mod.FitResult, options: SparcOptions) !void {
    _ = allocator; // autofix

    const stdout = std.io.getStdOut().writer();

    stdout.print("\n{s}Fit Results{s}\n", .{ colorize("=", .cyan), colorize("=", .cyan) }) catch unreachable;

    stdout.print("{s}Galaxy: {s}\n", .{ colorize("  ", .blue), if (options.galaxy_name.len > 0) options.galaxy_name else "Unknown" }) catch unreachable;
    stdout.print("\n", .{});

    stdout.print("{s}Savchenko Parameters:{s}\n", .{ colorize("  ", .magenta), colorize("", .reset) }) catch unreachable;
    stdout.print("{s}  ρ₀:      {d:.4e} M☉/pc³\n", .{ colorize("  ", .blue), result.params.rho0 }) catch unreachable;
    stdout.print("{s}  r_mem:    {d:.4e} kpc\n", .{ colorize("  ", .blue), result.params.r_mem }) catch unreachable;
    stdout.print("{s}  r_core:   {d:.4e} kpc\n", .{ colorize("  ", .blue), result.params.r_core }) catch unreachable;
    stdout.print("{s}  Υ_bul:    {d:.4e}\n", .{ colorize("  ", .blue), result.params.upsilon_bul }) catch unreachable;

    stdout.print("\n", .{});
    stdout.print("{s}Fit Quality:{s}\n", .{ colorize("  ", .magenta), colorize("", .reset) }) catch unreachable;
    stdout.print("{s}  χ²:         {d:.6f}\n", .{ colorize("  ", .blue), result.chi_squared }) catch unreachable;
    stdout.print("{s}  DOF:         {}\n", .{ colorize("  ", .blue), result.dof }) catch unreachable;
    stdout.print("{s}  Reduced χ²: {d:.6f}\n", .{ colorize("  ", .blue), result.reduced_chi_squared }) catch unreachable;

    // Quality indicator
    const is_good = Fitting.isGoodFit(result);
    const quality_str = if (is_good) colorize("GOOD", .green) else colorize("POOR", .red);
    stdout.print("\n{s}Quality: {s}{s}\n", .{ colorize("  ", .magenta), quality_str, colorize("", .reset) }) catch unreachable;
}

/// Output fit results in JSON format
fn outputJson(allocator: Allocator, result: mod.FitResult, points: []const mod.GalaxyDataPoint) !void {
    const stdout = std.io.getStdOut().writer();

    const root = std.ArrayList(json.Value).initCapacity(allocator, 10);
    defer root.deinit();

    // Parameters object
    var params_obj = std.StringHashMap(json.Value).init(allocator);
    defer params_obj.deinit();

    try params_obj.put("rho0", json.Value{ .float = result.params.rho0 });
    try params_obj.put("r_mem", json.Value{ .float = result.params.r_mem });
    try params_obj.put("r_core", json.Value{ .float = result.params.r_core });
    try params_obj.put("upsilon_bul", json.Value{ .float = result.params.upsilon_bul });

    // Result object
    var result_obj = std.StringHashMap(json.Value).init(allocator);
    defer result_obj.deinit();

    try result_obj.put("params", json.Value{ .object = params_obj });
    try result_obj.put("chi_squared", json.Value{ .float = result.chi_squared });
    try result_obj.put("degrees_of_freedom", json.Value{ .integer = @intCast(result.dof) });
    try result_obj.put("reduced_chi_squared", json.Value{ .float = result.reduced_chi_squared });
    try result_obj.put("is_good_fit", json.Value{ .bool = Fitting.isGoodFit(result) });

    // Output array
    var data_array = std.ArrayList(json.Value).initCapacity(allocator, points.len);
    defer data_array.deinit();

    for (points) |point| {
        var data_obj = std.StringHashMap(json.Value).init(allocator);
        defer data_obj.deinit();

        try data_obj.put("radius_kpc", json.Value{ .float = point.radius });
        try data_obj.put("velocity_kms", json.Value{ .float = point.velocity });
        try data_obj.put("velocity_err_kms", json.Value{ .float = point.velocity_err });

        try data_array.append(json.Value{ .object = data_obj });
    }

    var output_obj = std.StringHashMap(json.Value).init(allocator);
    defer output_obj.deinit();

    try output_obj.put("result", json.Value{ .object = result_obj });
    try output_obj.put("data_points", json.Value{ .array = data_array });

    // Write as compact JSON
    try stdout.print("{s}\n", .{try json.stringifyAlloc(allocator, json.Value{ .object = output_obj }, .{ .minify = true })});
}

/// Output fit results in CSV format
fn outputCsv(allocator: Allocator, result: mod.FitResult, points: []const mod.GalaxyDataPoint) !void {
    _ = allocator; // autofix
    const stdout = std.io.getStdOut().writer();

    // Header
    stdout.print("rho0,r_mem,r_core,upsilon_bul,chi_squared,dof,reduced_chi_squared\n", .{});
    stdout.print("{e},{e},{e},{e},{e},{},{e}\n", .{
        result.params.rho0,
        result.params.r_mem,
        result.params.r_core,
        result.params.upsilon_bul,
        result.chi_squared,
        result.dof,
        result.reduced_chi_squared,
    }) catch unreachable;

    // Data points header
    stdout.print("\nradius_kpc,velocity_kms,velocity_err_kms\n", .{});
    for (points) |point| {
        stdout.print("{e},{e},{e}\n", .{
            point.radius,
            point.velocity,
            point.velocity_err,
        }) catch unreachable;
    }
}

/// Run list command (placeholder - lists available galaxies)
fn runList(allocator: Allocator, options: SparcOptions) !void {
    _ = allocator;
    _ = options; // autofix

    const stdout = std.io.getStdOut().writer();

    stdout.print("Available galaxies:\n", .{});
    stdout.print("  NGC 2403 - 175 data points\n", .{});
    stdout.print("  (Download real data from astroweb.case.edu)\n", .{});
}

/// Run plot command (placeholder - ASCII plot)
fn runPlot(allocator: Allocator, options: SparcOptions) !void {
    _ = allocator; // autofix

    const stdout = std.io.getStdOut().writer();

    stdout.print("ASCII plot not yet implemented.\n", .{});
    stdout.print("Use --format json and pipe to external plotter.\n", .{});
}

/// Argument parsing error set
pub const ParseError = error{
    NoCommand,
    UnknownCommand,
    MissingFormatValue,
    UnknownFormat,
    MissingProfileValue,
    UnknownProfile,
    MissingDrValue,
    InvalidDrValue,
    MultipleGalaxyNames,
    NoData,
};
