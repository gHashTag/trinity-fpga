//! VIBEE Codegen Phase 1 - Extracts implementations and types from .tri specs
//! Generates complete Zig code with types and implementations
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");

const MAX_FIELDS = 32;
const MAX_IMPL_LINES = 256;

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    const allocator = gpa.allocator();

    const args = try std.process.argsAlloc(allocator);
    defer std.process.argsFree(allocator, args);

    if (args.len < 2) {
        std.debug.print("Usage: {s} <spec.tri> [output.zig]\n", .{args[0]});
        return error.Usage;
    }

    const spec_path = args[1];
    const output_path = if (args.len > 2) args[2] else try std.fmt.allocPrint(allocator, "{s}.zig", .{std.fs.path.stem(spec_path)});

    // Read spec file
    const file = try std.fs.cwd().openFile(spec_path, .{});
    defer file.close();
    const source = try file.readToEndAlloc(allocator, 10 * 1024 * 1024);
    defer allocator.free(source);

    // Write output file
    const out_file = try std.fs.cwd().createFile(output_path, .{});
    defer out_file.close();

    // Write header
    try out_file.writeAll("// ═══════════════════════════════════════════════════════════════\n");
    try out_file.writeAll("// Generated from: ");
    try out_file.writeAll(std.fs.path.basename(spec_path));
    try out_file.writeAll("\n");
    try out_file.writeAll("// VIBEE Codegen Phase 1 - Implementations + Types\n");
    try out_file.writeAll("// ═══════════════════════════════════════════════════════════════\n");
    try out_file.writeAll("\n");

    try out_file.writeAll("const std = @import(\"std\");\n\n");

    // Sacred constants
    try out_file.writeAll("// Sacred Constants\n");
    try out_file.writeAll("pub const PHI: f64 = 1.618033988749895;\n");
    try out_file.writeAll("pub const PHI_SQ: f64 = 2.618033988749895;\n");
    try out_file.writeAll("pub const GOLDEN_IDENTITY: f64 = 3.0;\n");
    try out_file.writeAll("pub const PI: f64 = 3.14159265358979323846;\n");
    try out_file.writeAll("pub const E: f64 = 2.71828182845904523536;\n");
    try out_file.writeAll("\n");

    // Extract and write types
    try out_file.writeAll("// ═══════════════════════════════════════════════════════════════\n");
    try out_file.writeAll("// TYPES\n");
    try out_file.writeAll("// ═══════════════════════════════════════════════════════════════\n");
    try out_file.writeAll("\n");

    var lines = std.mem.splitScalar(u8, source, '\n');
    var in_types = false;
    var in_type_fields = false;
    var current_type_name: []const u8 = "";
    var type_field_count: usize = 0;
    var type_fields: [MAX_FIELDS][]const u8 = undefined;

    while (lines.next()) |line| {
        const trimmed = std.mem.trim(u8, line, &std.ascii.whitespace);
        const indent = countIndent(line);

        if (std.mem.startsWith(u8, trimmed, "types:")) {
            in_types = true;
        } else if (std.mem.startsWith(u8, trimmed, "behaviors:") or
            std.mem.startsWith(u8, trimmed, "functions:") or
            std.mem.startsWith(u8, trimmed, "constants:") or
            std.mem.startsWith(u8, trimmed, "constraints:"))
        {
            // End of types section - write pending type
            in_types = false;
            in_type_fields = false;
            if (current_type_name.len > 0) {
                try writeStruct(out_file, current_type_name, type_fields[0..type_field_count]);
                current_type_name = "";
                type_field_count = 0;
            }
        } else if (in_types) {
            // Type definition at indent 2: "  TypeName:"
            if (indent == 2 and trimmed.len > 0 and trimmed[trimmed.len - 1] == ':') {
                // Save previous type if any
                if (current_type_name.len > 0) {
                    try writeStruct(out_file, current_type_name, type_fields[0..type_field_count]);
                    type_field_count = 0;
                }
                // Extract type name (remove trailing colon)
                current_type_name = trimmed[0 .. trimmed.len - 1];
                in_type_fields = false;
            }
            // Check for fields: section
            else if (indent >= 4 and std.mem.startsWith(u8, trimmed, "fields:")) {
                in_type_fields = true;
            }
            // Check for enum values
            else if (indent >= 4 and std.mem.startsWith(u8, trimmed, "values:")) {
                in_type_fields = true;
            }
            // Field definition: "    - name: field_name"
            else if (in_type_fields and indent >= 6 and std.mem.startsWith(u8, trimmed, "- name:")) {
                const name_start = std.mem.indexOf(u8, trimmed, "- name:").?;
                const name_val = trimmed[name_start + 7 ..];
                const field_name = std.mem.trim(u8, name_val, &std.ascii.whitespace);

                // Look ahead for type
                var field_type: []const u8 = "void";
                var next_s = lines.peek();
                while (next_s) |next_line| {
                    const next_indent = countIndent(next_line);
                    if (next_indent >= 8) {
                        const next_trimmed = std.mem.trim(u8, next_line, &std.ascii.whitespace);
                        if (std.mem.startsWith(u8, next_trimmed, "type:")) {
                            const type_start = std.mem.indexOf(u8, next_trimmed, "type:").?;
                            const type_val = next_trimmed[type_start + 6 ..];
                            field_type = std.mem.trim(u8, type_val, " \t");
                        }
                        _ = lines.next();
                        next_s = lines.peek();
                    } else {
                        break;
                    }
                }

                if (field_name.len > 0 and type_field_count < MAX_FIELDS) {
                    type_fields[type_field_count] = try std.fmt.allocPrint(allocator, "{s}: {s},", .{ field_name, field_type });
                    type_field_count += 1;
                }
            }
        }
    }

    // Write last type if any
    if (current_type_name.len > 0) {
        try writeStruct(out_file, current_type_name, type_fields[0..type_field_count]);
    }

    // Implementations
    try out_file.writeAll("\n");
    try out_file.writeAll("// ═══════════════════════════════════════════════════════════════\n");
    try out_file.writeAll("// IMPLEMENTATIONS\n");
    try out_file.writeAll("// ═══════════════════════════════════════════════════════════════\n");
    try out_file.writeAll("\n");

    // Reset line iterator for implementations
    lines = std.mem.splitScalar(u8, source, '\n');
    var in_implementation = false;
    var current_impl_name: []const u8 = "";
    var behavior_count: usize = 0;
    var impl_line_count: usize = 0;
    var impl_lines: [MAX_IMPL_LINES][]const u8 = undefined;

    while (lines.next()) |line| {
        const trimmed = std.mem.trim(u8, line, &std.ascii.whitespace);

        // Check for behavior start
        if (std.mem.startsWith(u8, trimmed, "- name:")) {
            // Save previous implementation if any
            if (in_implementation and impl_line_count > 0) {
                if (std.mem.indexOf(u8, impl_lines[0], "pub fn") != null) {
                    try writeImplementation(out_file, current_impl_name, impl_lines[0..impl_line_count]);
                    behavior_count += 1;
                }
                impl_line_count = 0;
            }

            const name_start = std.mem.indexOf(u8, trimmed, "- name:") orelse continue;
            const name_val = trimmed[name_start + 7 ..];
            const trimmed_name = std.mem.trim(u8, name_val, &std.ascii.whitespace);
            current_impl_name = trimmed_name;
            in_implementation = false;
        } else if (std.mem.startsWith(u8, trimmed, "implementation: |")) {
            in_implementation = true;
        } else if (in_implementation) {
            const indent = countIndent(line);
            if (indent >= 4) {
                var code_line = std.mem.trimLeft(u8, line, " \t");
                code_line = std.mem.trimRight(u8, code_line, " \t");
                if (code_line.len > 0 and impl_line_count < MAX_IMPL_LINES) {
                    impl_lines[impl_line_count] = try allocator.dupe(u8, code_line);
                    impl_line_count += 1;
                }
            } else if (trimmed.len > 0) {
                in_implementation = false;
                if (impl_line_count > 0 and std.mem.indexOf(u8, impl_lines[0], "pub fn") != null) {
                    try writeImplementation(out_file, current_impl_name, impl_lines[0..impl_line_count]);
                    behavior_count += 1;
                }
                impl_line_count = 0;
            }
        }
    }

    // Save last implementation
    if (impl_line_count > 0 and std.mem.indexOf(u8, impl_lines[0], "pub fn") != null) {
        try writeImplementation(out_file, current_impl_name, impl_lines[0..impl_line_count]);
        behavior_count += 1;
    }

    std.debug.print("✓ Generated: {s}\n", .{output_path});
    std.debug.print("  Types: {d}, Implementations: {d}\n", .{ behavior_count, behavior_count });
}

fn countIndent(line: []const u8) usize {
    var count: usize = 0;
    for (line) |c| {
        if (c == ' ') count += 1 else break;
    }
    return count;
}

fn writeStruct(out_file: std.fs.File, name: []const u8, fields: []const []const u8) !void {
    try out_file.writeAll("pub const ");
    try out_file.writeAll(name);
    try out_file.writeAll(" = struct {\n");

    for (fields) |field| {
        try out_file.writeAll("    ");
        try out_file.writeAll(field);
        try out_file.writeAll("\n");
    }

    try out_file.writeAll("};\n\n");
}

fn writeImplementation(out_file: std.fs.File, name: []const u8, lines: []const []const u8) !void {
    try out_file.writeAll("// ");
    try out_file.writeAll(name);
    try out_file.writeAll("\n");

    for (lines) |line| {
        try out_file.writeAll(line);
        try out_file.writeAll("\n");
    }
    try out_file.writeAll("\n");
}
