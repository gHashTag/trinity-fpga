//! Compile-time Data Embedding
//! φ² + 1/φ² = 3 | TRINITY
//!
//! Provides compile-time embedding of SPARC data using @embedFile.
//! Enables offline operation without network access.

const std = @import("std");
const Allocator = std.mem.Allocator;

/// Embedded SPARC data (if available at compile time)
///
/// To enable data embedding, place SPARC data file at:
///   var/trinity/sparc/embedded_data.txt
///
/// Then rebuild: zig build tri
///
/// The data will be embedded in the binary and available offline.
pub const embedded_data = if (@embedFile("var/trinity/sparc/embedded_data.txt").len > 0)
    @embedFile("var/trinity/sparc/embedded_data.txt")
else
    "";

/// Check if embedded data is available
pub fn hasEmbeddedData() bool {
    return embedded_data.len > 0;
}

/// Get embedded data as string slice
///
/// # Returns
///   Embedded data content (or empty string if not available)
pub fn getEmbeddedData() []const u8 {
    return embedded_data[0..];
}

/// Create embedded data file placeholder
///
/// This should be called during build if embedded data doesn't exist.
pub fn ensureEmbeddedPlaceholder(allocator: Allocator) !void {
    _ = allocator; // autofix

    if (hasEmbeddedData()) return;

    const path = "var/trinity/sparc/embedded_data.txt";
    std.fs.cwd().makePath("var/trinity/sparc") catch {};

    if (std.fs.cwd().openFile(path, .{})) |file| {
        file.close();
        return;
    } else |_| {}

    // Create placeholder
    const file = try std.fs.cwd().createFile(path, .{});
    defer file.close();

    const content =
        \\# SPARC Embedded Data Placeholder
        \\# This file will be populated with actual SPARC data
        \\#
        \\# To embed real data:
        \\# 1. Run: tri sparc download
        \\# 2. Copy downloaded data to this file
        \\# 3. Rebuild: zig build tri
        \\
        \\# Format: R[kpc] V[km/s] err_V[km/s]
        \\0.0 0.0 0.0
    ;

    _ = try file.writeAll(content);
}

test "hasEmbeddedData returns boolean" {
    const has = hasEmbeddedData();
    _ = has; // Just verify it compiles
}

test "getEmbeddedData returns slice" {
    const data = getEmbeddedData();
    _ = data; // Just verify it compiles
}
