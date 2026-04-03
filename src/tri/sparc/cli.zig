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

    // Check if this is batch mode (no galaxy specified) or single galaxy mode
    if (options.galaxy_name.len == 0) {
        // Batch mode: fit all galaxies
        return runBatchFit(allocator, data_content, options);
    }

    // Single galaxy mode
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

/// Batch fit all galaxies and output summary statistics
fn runBatchFit(allocator: Allocator, data_content: []const u8, options: SparcOptions) !void {
    const stdout = std.io.getStdOut().writer();

    stdout.print("\n{s}SPARC Batch Fit{ s}\n", .{ colorize("════════════════════════════════════════════════════════════", .cyan), colorize("", .reset) });
    stdout.print("{s}Fitting Savchenko model to all galaxies...{s}\n\n", .{
        colorize("", .yellow), colorize("", .reset),
    });

    const galaxies = try Data.parseAllGalaxies(allocator, data_content);
    defer {
        for (galaxies) |*g| g.deinit(allocator);
        allocator.free(galaxies);
    }

    if (galaxies.len == 0) {
        stdout.print("No galaxies found in dataset.\n", .{});
        return error.NoData;
    }

    stdout.print("Found {d} galaxies to fit...\n\n", .{galaxies.len});

    var results = std.ArrayList(struct {
        name: []const u8,
        chi_sq: f64,
        reduced_chi_sq: f64,
        is_good: bool,
        num_points: usize,
    }).init(allocator);
    defer results.deinit();

    var total_good: usize = 0;
    var total_chi_sum: f64 = 0;
    var chi_values = std.ArrayList(f64).init(allocator);
    defer chi_values.deinit();

    for (galaxies, 0..) |galaxy, i| {
        if (options.verbose) {
            stdout.print("[{d:0>3}/{d:0>3}] Fitting {s}... ", .{ i + 1, galaxies.len, galaxy.name });
        }

        const result = Fitting.fitGalaxy(allocator, galaxy.points) catch |err| {
            if (options.verbose) {
                stdout.print("FAILED: {}\n", .{err});
            }
            continue;
        };

        const is_good = Fitting.isGoodFit(result);
        if (is_good) total_good += 1;

        total_chi_sum += result.reduced_chi_squared;
        try chi_values.append(result.reduced_chi_squared);

        try results.append(.{
            .name = galaxy.name,
            .chi_sq = result.chi_squared,
            .reduced_chi_sq = result.reduced_chi_squared,
            .is_good = is_good,
            .num_points = galaxy.points.len,
        });

        if (options.verbose) {
            const status = if (is_good) colorize("GOOD", .green) else colorize("POOR", .red);
            stdout.print("{s} (χ²={d:.3f})\n", .{ status, result.reduced_chi_squared });
        } else {
            // Simple progress indicator
            if ((i + 1) % 10 == 0 or i + 1 == galaxies.len) {
                stdout.print("\rProgress: {d}/{d} galaxies fitted", .{ i + 1, galaxies.len });
            }
        }
    }

    stdout.print("\n\n", .{});

    // Calculate median χ²
    const median_chi = if (chi_values.items.len > 0) blk: {
        // Simple median calculation
        std.sort.insert(f64, chi_values.items, {}, struct {
            fn lessThan(_: void, a: f64, b: f64) bool {
                return a < b;
            }
        }.lessThan);
        const mid = chi_values.items.len / 2;
        if (chi_values.items.len % 2 == 0) {
            break :blk (chi_values.items[mid - 1] + chi_values.items[mid]) / 2;
        } else {
            break :blk chi_values.items[mid];
        }
    } else 0;

    const mean_chi = if (results.items.len > 0) total_chi_sum / @as(f64, @floatFromInt(results.items.len)) else 0;

    // Print summary
    stdout.print("{s}Batch Fit Summary{s}\n", .{ colorize("════════════════════════════════════════════════════════════", .cyan), colorize("", .reset) });
    stdout.print("\n", .{});
    stdout.print("  Total galaxies: {d}\n", .{results.items.len});
    stdout.print("  Good fits (χ² < 2.0): {d} ({d:.1f}%)\n", .{ total_good, if (results.items.len > 0) @as(f64, @floatFromInt(total_good)) / @as(f64, @floatFromInt(results.items.len)) * 100 else 0 });
    stdout.print("  Mean reduced χ²: {d:.3f}\n", .{mean_chi});
    stdout.print("  Median reduced χ²: {d:.3f}\n", .{median_chi});
    stdout.print("\n", .{});

    // Quality indicator
    const quality_threshold: f64 = 0.97; // 97% good fits target
    const success_rate = if (results.items.len > 0)
        @as(f64, @floatFromInt(total_good)) / @as(f64, @floatFromInt(results.items.len))
    else
        0;

    const status_str = if (success_rate >= quality_threshold)
        colorize("EXCELLENT", .green)
    else if (success_rate >= 0.8)
        colorize("GOOD", .yellow)
    else
        colorize("POOR", .red);

    stdout.print("  Overall quality: {s} ({d:.1f}% good fits){s}\n\n", .{ status_str, success_rate * 100, colorize("", .reset) });

    // Output detailed results based on format
    switch (options.format) {
        .text => {
            if (!options.verbose) {
                stdout.print("Use --verbose for per-galaxy details.\n", .{});
            }
        },
        .json => {
            const root = std.ArrayList(json.Value).initCapacity(allocator, results.items.len);
            defer root.deinit();

            var summary_obj = std.StringHashMap(json.Value).init(allocator);
            defer summary_obj.deinit();

            try summary_obj.put("total_galaxies", json.Value{ .integer = @intCast(results.items.len) });
            try summary_obj.put("good_fits", json.Value{ .integer = @intCast(total_good) });
            try summary_obj.put("good_fit_percentage", json.Value{ .float = success_rate * 100 });
            try summary_obj.put("mean_reduced_chi_squared", json.Value{ .float = mean_chi });
            try summary_obj.put("median_reduced_chi_squared", json.Value{ .float = median_chi });

            var results_array = std.ArrayList(json.Value).initCapacity(allocator, results.items.len);
            defer results_array.deinit();

            for (results) |r| {
                var r_obj = std.StringHashMap(json.Value).init(allocator);
                defer r_obj.deinit();

                try r_obj.put("name", json.Value{ .string = r.name });
                try r_obj.put("chi_squared", json.Value{ .float = r.chi_sq });
                try r_obj.put("reduced_chi_squared", json.Value{ .float = r.reduced_chi_sq });
                try r_obj.put("is_good_fit", json.Value{ .bool = r.is_good });
                try r_obj.put("num_points", json.Value{ .integer = @intCast(r.num_points) });

                try results_array.append(json.Value{ .object = r_obj });
            }

            var output_obj = std.StringHashMap(json.Value).init(allocator);
            defer output_obj.deinit();

            try output_obj.put("summary", json.Value{ .object = summary_obj });
            try output_obj.put("results", json.Value{ .array = results_array });

            try stdout.print("{s}\n", .{try json.stringifyAlloc(allocator, json.Value{ .object = output_obj }, .{ .minify = false })});
        },
        .csv => {
            stdout.print("name,chi_squared,reduced_chi_squared,is_good_fit,num_points\n", .{});
            for (results) |r| {
                const good_str = if (r.is_good) "true" else "false";
                stdout.print("{s},{e},{e},{s},{}\n", .{
                    r.name, r.chi_sq, r.reduced_chi_sq, good_str, r.num_points,
                });
            }
        },
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

/// Run list command (lists available galaxies)
fn runList(allocator: Allocator, options: SparcOptions) !void {
    const stdout = std.io.getStdOut().writer();

    // Download or load data
    const data_content = try Data.downloadSPARCData(allocator, options.use_cache);
    defer allocator.free(data_content);

    const galaxies = try Data.parseAllGalaxies(allocator, data_content);
    defer {
        for (galaxies) |*g| g.deinit(allocator);
        allocator.free(galaxies);
    }

    if (galaxies.len == 0) {
        stdout.print("No galaxies found in dataset.\n", .{});
        return;
    }

    switch (options.format) {
        .text => {
            stdout.print("\n{s}SPARC Galaxies ({d} found){s}\n\n", .{
                colorize("╔════════════════════════════════════════════════════════════════╗\n", .cyan),
                galaxies.len,
                colorize("╚════════════════════════════════════════════════════════════════╝", .cyan),
            });

            stdout.print("{s}Name{s}     Points  Dist  Inc  PA\n", .{
                colorize("────────────────────────────────────────────────────────────", .cyan),
                colorize("", .reset),
            });

            for (galaxies) |galaxy| {
                const name_fmt = if (galaxy.name.len < 12)
                    std.fmt.comptimePrint("{s}" ** 12, .{" "}) ++ galaxy.name
                else
                    galaxy.name[0..12];

                stdout.print("{s} {d: >6}  {d:>4.1f}  {d:>3.0f}  {d:>3.0f}\n", .{
                    colorize(name_fmt, .blue),
                    galaxy.points.len,
                    galaxy.distance,
                    galaxy.inclination,
                    galaxy.position_angle,
                });
            }
            stdout.print("\n  Dist: Mpc, Inc: degrees, PA: degrees\n\n", .{});
        },
        .json => {
            const root = std.ArrayList(json.Value).initCapacity(allocator, galaxies.len);
            defer root.deinit();

            for (galaxies) |galaxy| {
                var galaxy_obj = std.StringHashMap(json.Value).init(allocator);
                defer galaxy_obj.deinit();

                try galaxy_obj.put("name", json.Value{ .string = galaxy.name });
                try galaxy_obj.put("points", json.Value{ .integer = @intCast(galaxy.points.len) });
                try galaxy_obj.put("distance_mpc", json.Value{ .float = galaxy.distance });
                try galaxy_obj.put("inclination_deg", json.Value{ .float = galaxy.inclination });
                try galaxy_obj.put("position_angle_deg", json.Value{ .float = galaxy.position_angle });

                try root.append(json.Value{ .object = galaxy_obj });
            }

            try stdout.print("{s}\n", .{try json.stringifyAlloc(allocator, json.Value{ .array = root }, .{ .minify = false })});
        },
        .csv => {
            stdout.print("name,points,distance_mpc,inclination_deg,position_angle_deg\n", .{});
            for (galaxies) |galaxy| {
                stdout.print("{s},{d},{e},{e},{e}\n", .{
                    galaxy.name,
                    galaxy.points.len,
                    galaxy.distance,
                    galaxy.inclination,
                    galaxy.position_angle,
                });
            }
        },
    }
}

/// Run plot command (ASCII-art rotation curve plot)
fn runPlot(allocator: Allocator, options: SparcOptions) !void {
    const stdout = std.io.getStdOut().writer();

    if (options.galaxy_name.len == 0) {
        stdout.print("Error: Please specify a galaxy name for plotting.\n", .{});
        stdout.print("Usage: tri sparc plot <galaxy_name>\n", .{});
        return error.MissingGalaxyName;
    }

    // Download or load data
    const data_content = try Data.downloadSPARCData(allocator, options.use_cache);
    defer allocator.free(data_content);

    const points = try Data.parseSPARCData(allocator, data_content);
    defer allocator.free(points);

    if (points.len == 0) {
        stdout.print("No data points found.\n", .{});
        return error.NoData;
    }

    // Get fit result
    const result = try Fitting.fitGalaxy(allocator, points);

    // ASCII plot settings
    const PLOT_WIDTH: usize = 60;
    const PLOT_HEIGHT: usize = 20;

    // Find ranges
    var max_r: f64 = 0;
    var max_v: f64 = 0;
    for (points) |p| {
        if (p.radius > max_r) max_r = p.radius;
        if (p.velocity > max_v) max_v = p.velocity;
    }

    stdout.print("\n{s}Rotation Curve: {s}{s}\n", .{
        colorize("══════════════════════════════════════════════════════════════════\n", .cyan),
        options.galaxy_name,
        colorize("", .reset),
    });

    // Print legend
    stdout.print("{s}●{s} Observed data  {s}─{s} Savchenko model\n\n", .{
        colorize("", .blue), colorize("", .reset),
        colorize("", .green), colorize("", .reset),
    });

    // Create plot grid (y-axis = velocity, x-axis = radius)
    // Render from top (max velocity) to bottom (0)
    for (0..PLOT_HEIGHT) |y| {
        const v_at_y = max_v - (@as(f64, @floatFromInt(y)) / @as(f64, @floatFromInt(PLOT_HEIGHT - 1))) * max_v;

        // Y-axis label
        if (y % 5 == 0) {
            stdout.print("{d:4.0f} |", .{v_at_y});
        } else {
            stdout.print("      |", .{});
        }

        // Draw row
        var row_buffer: [PLOT_WIDTH]u8 = undefined;
        @memset(&row_buffer, ' ');
        for (0..PLOT_WIDTH) |x| {
            const r_at_x = @as(f64, @floatFromInt(x)) / @as(f64, @floatFromInt(PLOT_WIDTH - 1)) * max_r;

            // Check for observed data points nearby
            for (points) |p| {
                const x_pos = @as(usize, @intFromFloat((p.radius / max_r) * @as(f64, @floatFromInt(PLOT_WIDTH - 1))));
                const v_pos = PLOT_HEIGHT - 1 - @as(usize, @intFromFloat((p.velocity / max_v) * @as(f64, @floatFromInt(PLOT_HEIGHT - 1))));

                if (x == x_pos and y == v_pos) {
                    row_buffer[x] = '●'; // Data point
                    break;
                }
            }

            // If no data point, check for model line
            if (row_buffer[x] == ' ') {
                const model_v = Savchenko.totalVelocity(
                    allocator,
                    r_at_x,
                    result.params.rho0,
                    result.params.r_mem,
                    result.params.r_core,
                    // Rough estimate of disk velocity at this radius
                    if (points.len > 0) blk: {
                        const idx = @min(points.len - 1, @as(usize, @intFromFloat((r_at_x / max_r) * @as(f64, @floatFromInt(points.len)))));
                        break :blk points[idx].velocity;
                    } else 0,
                    0,
                    0.1,
                ) catch 0;

                const model_y = PLOT_HEIGHT - 1 - @as(usize, @intFromFloat((model_v / max_v) * @as(f64, @floatFromInt(PLOT_HEIGHT - 1))));

                if (y == model_y or (y + 1 == model_y and model_y < PLOT_HEIGHT)) {
                    row_buffer[x] = '─'; // Model line
                }
            }
        }

        // Print row
        for (row_buffer) |c| {
            if (c == '●') {
                stdout.print("{s}●{s}", .{ colorize("", .blue), colorize("", .reset) });
            } else if (c == '─') {
                stdout.print("{s}─{s}", .{ colorize("", .green), colorize("", .reset) });
            } else {
                stdout.print(" ", .{});
            }
        }
        stdout.print("\n", .{});
    }

    // X-axis
    stdout.print("      +", .{});
    for (0..PLOT_WIDTH) |_| {
        stdout.print("─", .{});
    }
    stdout.print("\n", .{});

    // X-axis labels
    stdout.print("     0.0", .{});
    stdout.print(" {d: >40.1f} kpc (R)\n", .{max_r});

    // Print fit parameters below
    stdout.print("\n{s}Fit Parameters:{s}\n", .{ colorize("", .magenta), colorize("", .reset) });
    stdout.print("  ρ₀:      {d:.4e} M☉/pc³\n", .{result.params.rho0});
    stdout.print("  r_mem:   {d:.4e} kpc\n", .{result.params.r_mem});
    stdout.print("  r_core:  {d:.4e} kpc\n", .{result.params.r_core});
    stdout.print("  Υ_bul:   {d:.4e}\n", .{result.params.upsilon_bul});
    stdout.print("  χ²:      {d:.4f} (reduced: {d:.4f})\n", .{result.chi_squared, result.reduced_chi_squared});
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
    MissingGalaxyName,
    NoData,
};
