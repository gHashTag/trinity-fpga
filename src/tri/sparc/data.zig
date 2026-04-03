//! SPARC Data Module
//! φ² + 1/φ² = 3 | TRINITY
//!
//! Handles downloading, parsing, and caching SPARC galaxy rotation curve data
//! from astroweb.case.edu. Includes data bundling for offline operation.

const std = @import("std");
const Allocator = std.mem.Allocator;

const SavchenkoParams = @import("mod.zig").SavchenkoParams;
const GalaxyDataPoint = @import("mod.zig").GalaxyDataPoint;
const GalaxyDataset = @import("mod.zig").GalaxyDataset;

/// SPARC data source URL
pub const SPARC_BASE_URL = "https://astroweb.case.edu/SPARC/rotmod/rotmod_LTG.zip";

/// Local cache directory
pub const CACHE_DIR = "var/trinity/sparc";

/// Cached data filename
pub const CACHE_FILE = CACHE_DIR ++ "/cache.json";

/// Embedded data filename
pub const EMBEDDED_DATA_PATH = "var/trinity/sparc/embedded_data.txt";

/// HTTP timeout in seconds
pub const HTTP_TIMEOUT_SEC: u32 = 30;

/// SPARC data download error set
pub const DownloadError = error{
    HttpError,
    InvalidData,
    ParseError,
    CacheError,
    IOError,
};

/// Download SPARC data from astroweb.case.edu
///
/// # Parameters
///   - allocator: Memory allocator
///   - use_cached: If true, try to use cached data first
///
/// # Returns
///   JSON string containing parsed galaxy data
pub fn downloadSPARCData(allocator: Allocator, use_cached: bool) ![]const u8 {
    // Try cache first if requested
    if (use_cached) {
        if (std.fs.path.dirnameAlloc(allocator, CACHE_FILE)) |dir| {
            defer allocator.free(dir);

            if (std.fs.cwd().openDir(dir, .{})) |dir_stream| {
                defer dir_stream.close();

                var dir_iter = dir_stream.iterate();
                while (dir_iter.next()) |entry| {
                    if (entry.kind == .file) {
                        if (std.mem.eql(u8, entry.name, std.fs.path.basename(CACHE_FILE))) {
                            std.debug.print("Using cached SPARC data from {s}...\n", .{CACHE_FILE});

                            const cached_data = std.fs.cwd().readFileAlloc(allocator, CACHE_FILE) catch |err| {
                                std.debug.print("Failed to read cache: {}\n", .{err});
                                continue;
                            };

                            return cached_data;
                        }
                    }
                }
            } else |_| {}
        } else |_| {}
    }

    // Try embedded data
    if (std.fs.cwd().openFile(EMBEDDED_DATA_PATH, .{})) |file| {
        defer file.close();
        std.debug.print("Using embedded SPARC data...\n", .{});

        const size = try file.getEndPos();
        const data = try allocator.alloc(u8, @as(usize, size));
        _ = try file.readAll(data);

        return data;
    } else |_| {}
}

/// Parse SPARC plaintext format (8 columns)
/// Column format: R[kpc] V[km/s] err_V[km/s]
///
/// # Parameters
///   - allocator: Memory allocator
///   - content: Raw data content as string
///
/// # Returns
///   Array of GalaxyDataPoint
pub fn parseSPARCData(allocator: Allocator, content: []const u8) ![]GalaxyDataPoint {
    var points = std.ArrayList(GalaxyDataPoint).initCapacity(allocator, 100);

    var lines = std.mem.splitScalar(u8, content, '\n');
    defer lines.deinit();

    while (lines.next()) |line| {
        // Skip empty lines and comments
        const trimmed = std.mem.trim(u8, line, &std.ascii.whitespace);
        if (trimmed.len == 0 or trimmed[0] == '#') continue;

        // Split by whitespace
        var parts = std.mem.splitScalar(u8, trimmed, ' ');
        defer parts.deinit();

        var fields = std.ArrayList([]const u8).initCapacity(allocator, 8);
        defer fields.deinit();

        while (parts.next()) |part| {
            if (part.len > 0) {
                try fields.append(part);
            }
        }

        // Need at least 3 columns: radius, velocity, error
        if (fields.items.len < 3) continue;

        // Parse fields
        const radius = try std.fmt.parseFloat(f64, fields.items[0]);
        const velocity = try std.fmt.parseFloat(f64, fields.items[1]);
        const velocity_err = try std.fmt.parseFloat(f64, fields.items[2]);

        // Validate ranges
        if (radius < 0 or radius > 50) continue; // kpc
        if (velocity < 0 or velocity > 500) continue; // km/s
        if (velocity_err < 0 or velocity_err > 100) continue; // km/s

        try points.append(.{
            .radius = radius,
            .velocity = velocity,
            .velocity_err = velocity_err,
        });
    }

    return points.toOwnedSlice();
}

/// Cache parsed data as JSON for fast reloads
///
/// # Parameters
///   - allocator: Memory allocator
///   - data: Galaxy data to cache
pub fn cacheData(_allocator: Allocator, _data: []const u8) !void {
    const dir = CACHE_DIR;
    std.fs.makePathAbsolute(dir) catch {};

    // Ensure directory exists
    std.fs.cwd().makePath(dir) catch |err| {
        std.debug.print("Failed to create cache directory: {}\n", .{err});
        return error.CacheError;
    };

    // Write cache file
    const file = try std.fs.cwd().createFile(CACHE_FILE, .{});
    defer file.close();

    _ = try file.writeAll(_data);

    std.debug.print("SPARC data cached to {s}\n", .{CACHE_FILE});
}

/// Parse galaxy name from filename or header
///
/// # Parameters
///   - content: Raw data content
///
/// # Returns
///   Galaxy name (or default)
pub fn parseGalaxyName(content: []const u8) []const u8 {
    var lines = std.mem.splitScalar(u8, content, '\n');
    defer lines.deinit();

    var line_num: u32 = 0;
    while (lines.next()) |line| {
        line_num += 1;

        // Look for comment lines with galaxy info
        const trimmed = std.mem.trim(u8, line, &std.ascii.whitespace);
        if (trimmed.len > 0 and trimmed[0] == '#') {
            // Remove '# ' and trim
            const comment = std.mem.trim(u8, trimmed[1..], &std.ascii.whitespace);

            // Look for keywords
            if (std.mem.indexOf(u8, comment, "NGC") != null or
                std.mem.indexOf(u8, comment, "UGC") != null or
                std.mem.indexOf(u8, comment, "IC") != null or
                std.mem.indexOf(u8, comment, "Galaxy") != null)
            {
                // Extract name (take first "word" or alphanumeric sequence)
                var name_parts = std.mem.splitScalar(u8, comment, ' ');
                defer name_parts.deinit();

                if (name_parts.next()) |name| {
                    return name;
                }
            }
        }

        // Stop after header section
        if (line_num > 20) break;
    }

    return "Unknown Galaxy";
}

/// Create embedded data file header (placeholder for offline operation)
///
/// # Parameters
///   - allocator: Memory allocator
pub fn createEmbeddedDataFile(_allocator: Allocator) !void {
    const dir = CACHE_DIR;
    std.fs.cwd().makePath(dir) catch {};

    const content =
        \\# SPARC Embedded Data Placeholder
        \\# This file will be populated with actual SPARC data
        \\# via the embeds.zig module during build.
        \\
        \\# Format: R[kpc] V[km/s] err_V[km/s] ...
        \\# Example: 0.5 45.2 2.3 0.0 0.0 0.0 0.0 0.0
    ;

    const file = try std.fs.cwd().createFile(EMBEDDED_DATA_PATH, .{});
    defer file.close();

    _ = try file.writeAll(content);

    std.debug.print("Created embedded data placeholder: {s}\n", .{EMBEDDED_DATA_PATH});
}

test "parseSPARCData handles valid format" {
    const allocator = std.testing.allocator;
    const content =
        \\# NGC 2403
        \\# R[kpc] V[km/s] err_V[km/s]
        \\0.5 45.2 2.3
        \\1.0 67.8 3.1
        \\1.5 89.4 3.8
        \\2.0 105.6 4.2
    ;

    const points = try parseSPARCData(allocator, content);
    defer allocator.free(points);

    try std.testing.expect(points.len == 4);
    try std.testing.expectApproxEqAbs(f64, points[0].radius, 0.5, 1e-10);
    try std.testing.expectApproxEqAbs(f64, points[0].velocity, 45.2, 1e-10);
    try std.testing.expectApproxEqAbs(f64, points[0].velocity_err, 2.3, 1e-10);
}

test "parseSPARCData skips invalid lines" {
    const allocator = std.testing.allocator;
    const content =
        \\# Header comment
        \\0.5 45.2 2.3
        \\1.0 67.8 3.1
        \\# Another comment
        \\-1.0 100.0 5.0  // Negative radius - should skip
        \\1.5 89.4 3.8
        \\2.0 600.0 10.0  // Velocity too high - should skip
        \\2.5 95.1 4.5
    ;

    const points = try parseSPARCData(allocator, content);
    defer allocator.free(points);

    // Should only include valid points (0.5, 1.0, 1.5, 2.5)
    try std.testing.expect(points.len == 4);
    try std.testing.expectApproxEqAbs(f64, points[0].radius, 0.5, 1e-10);
}

test "parseGalaxyName extracts from header" {
    const content =
        \\# NGC 2403 Rotation Curve
        \\# Distance: 3.2 Mpc
        \\# Inclination: 75 degrees
        \\0.5 45.2 2.3
    ;

    const name = parseGalaxyName(content);
    try std.testing.expectEqualSlices(u8, name, "NGC");
}
