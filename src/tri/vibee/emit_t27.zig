// emit_t27: .tri spec → .t27 assembly code generator
// Part of VIBEE compiler pipeline
// φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const Allocator = std.mem.Allocator;
const ArrayList = std.ArrayListUnmanaged;

// VIBEE Parser types - imported as module
const vibeec = @import("vibeec");

pub const Constant = vibeec.Constant;
pub const TypeDef = vibeec.TypeDef;
pub const Field = vibeec.Field;
pub const Behavior = vibeec.Behavior;
pub const TestCase = vibeec.TestCase;
pub const VibeeSpec = vibeec.VibeeSpec;

// ============================================================================
// TRI-27 ASSEMBLY SPECIFICATION
// ============================================================================

// .t27 assembly format specification:
// - .const section: constant definitions
// - .data section: data labels (.word, .dword, .ascii)
// - .code section: instructions
//
// Registers: t0-t26 (27 registers in Coptic alphabet)
// Instructions:
//   LDI  dst, imm   - Load immediate (0-255)
//   LD   dst, src   - Load from memory (absolute address)
//   ST   dst, src   - Store to memory (absolute address)
//   MOV  dst, src   - Move register
//   ADD  dst, src   - Add
//   SUB  dst, src   - Subtract
//   MUL  dst, src   - Multiply
//   DIV  dst, src   - Divide (integer)
//   JZ   reg, label - Jump if zero
//   JNZ  reg, label - Jump if non-zero
//   JGE  reg, label - Jump if greater or equal
//   JGT  reg, label - Jump if greater than
//   JLT  reg, label - Jump if less than
//   JLE  reg, label - Jump if less or equal
//   JUMP label       - Unconditional jump
//   INC  reg         - Increment
//   DEC  reg         - Decrement
//   HALT             - Stop execution

// ============================================================================
// T27 CODE GENERATOR
// ============================================================================

pub const T27Emitter = struct {
    allocator: Allocator,
    code: ArrayList(u8),
    data: ArrayList(u8),
    consts: ArrayList(u8),
    label_counter: usize,

    pub fn init(allocator: Allocator) T27Emitter {
        return .{
            .allocator = allocator,
            .code = ArrayList(u8).init(allocator),
            .data = ArrayList(u8).init(allocator),
            .consts = ArrayList(u8).init(allocator),
            .label_counter = 0,
        };
    }

    pub fn deinit(self: *T27Emitter) void {
        self.code.deinit(self.allocator);
        self.data.deinit(self.allocator);
        self.consts.deinit(self.allocator);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SECTION HELPERS
    // ═══════════════════════════════════════════════════════════════════════

    fn emitConst(self: *T27Emitter, comptime fmt: []const u8, args: anytype) !void {
        const line = try std.fmt.allocPrint(self.allocator, fmt, args);
        defer self.allocator.free(line);
        try self.consts.appendSlice(line);
        try self.consts.append('\n');
    }

    fn emitData(self: *T27Emitter, comptime fmt: []const u8, args: anytype) !void {
        const line = try std.fmt.allocPrint(self.allocator, fmt, args);
        defer self.allocator.free(line);
        try self.data.appendSlice(line);
        try self.data.append('\n');
    }

    fn emitCode(self: *T27Emitter, comptime fmt: []const u8, args: anytype) !void {
        const line = try std.fmt.allocPrint(self.allocator, fmt, args);
        defer self.allocator.free(line);
        try self.code.appendSlice(line);
        try self.code.append('\n');
    }

    fn emitComment(self: *T27Emitter, comptime fmt: []const u8, args: anytype) !void {
        const line = try std.fmt.allocPrint(self.allocator, "; " ++ fmt, args);
        defer self.allocator.free(line);
        try self.code.appendSlice(line);
        try self.code.append('\n');
    }

    fn emitLabel(self: *T27Emitter, name: []const u8) !void {
        const line = try std.fmt.allocPrint(self.allocator, "{s}:", .{name});
        defer self.allocator.free(line);
        try self.code.appendSlice(line);
        try self.code.append('\n');
    }

    fn genLabel(self: *T27Emitter, prefix: []const u8) ![]const u8 {
        const label = try std.fmt.allocPrint(self.allocator, "{s}_{d}", .{ prefix, self.label_counter });
        self.label_counter += 1;
        return label;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // .CONST SECTION GENERATION
    // ═══════════════════════════════════════════════════════════════════════

    pub fn emitConsts(self: *T27Emitter, constants: []const Constant) !void {
        if (constants.len == 0) return;

        try self.emitConst("; TRI-27 Constants");
        try self.emitConst("; φ² + 1/φ² = 3 | TRINITY");

        for (constants) |c| {
            if (c.is_string) {
                try self.emitConst("{s}: .ascii \"{s}\"", .{ c.name, c.string_value });
            } else {
                // For numeric constants, emit as T27 immediate value
                const int_val: i64 = @intFromFloat(c.value);
                try self.emitConst("{s} = {d}", .{ c.name, int_val });
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // .DATA SECTION GENERATION
    // ═══════════════════════════════════════════════════════════════════════

    pub fn emitDataSection(self: *T27Emitter, spec: VibeeSpec) !void {
        try self.emitData("; Data section");
        try self.emitData("; Generated from {s}", .{spec.name});

        // Emit fields from each type as data labels
        for (spec.types.items) |t| {
            try self.emitData("");
            try self.emitData("; Type: {s}", .{t.name});
            for (t.fields.items) |f| {
                const type_size = self.getTypeSize(f.type_name);
                try self.emitData("{s}: .skip {d}", .{ f.name, type_size });
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // .CODE SECTION GENERATION
    // ═══════════════════════════════════════════════════════════════════════

    pub fn emitCodeSection(self: *T27Emitter, spec: VibeeSpec) !void {
        try self.emitCode("; Code section");
        try self.emitCode("; Generated from {s} v{s}", .{ spec.name, spec.version });
        try self.emitCode("; φ² + 1/φ² = 3 | TRINITY");
        try self.emitCode("");

        // Emit function entry point
        try self.emitLabel("main");
        try self.emitComment("Entry point for {s}", .{spec.name});

        // Emit behaviors as functions
        for (spec.behaviors.items) |b| {
            try self.emitBehavior(b);
        }

        // End
        try self.emitCode("");
        try self.emitCode("HALT");
    }

    fn emitBehavior(self: *T27Emitter, behavior: Behavior) !void {
        try self.emitCode("");
        try self.emitLabel(behavior.name);
        try self.emitComment("{s}", .{behavior.description});

        // If there's an implementation, parse and emit instructions
        if (behavior.implementation.len > 0) {
            try self.emitFormula(behavior.implementation);
        } else {
            try self.emitComment("; TODO: implement {s}", .{behavior.name});
            try self.emitCode("HALT");
        }
    }

    fn emitFormula(self: *T27Emitter, formula: []const u8) !void {
        // Simple formula parser - looks for patterns like:
        // "result = input * weight"
        // "sum += value"
        // "return result"

        var lines = std.mem.splitScalar(u8, formula, '\n');
        while (lines.next()) |line| {
            const trimmed = std.mem.trim(u8, line, " \t\r");
            if (trimmed.len == 0) continue;
            if (trimmed[0] == '#') continue; // Skip comments

            // Try to parse as assignment
            if (std.mem.indexOfScalar(u8, trimmed, '=')) |eq_idx| {
                const lhs = std.mem.trim(u8, trimmed[0..eq_idx], " ");
                var rhs = std.mem.trim(u8, trimmed[eq_idx + 1 ..], " ");

                // Handle += operator
                if (std.mem.endsWith(u8, lhs, "+")) {
                    const target = std.mem.trimRight(u8, lhs, "+ ");
                    try self.emitCode("ADD {s}, {s}", .{ target, rhs });
                }
                // Handle -= operator
                else if (std.mem.endsWith(u8, lhs, "-")) {
                    const target = std.mem.trimRight(u8, lhs, "- ");
                    try self.emitCode("SUB {s}, {s}", .{ target, rhs });
                }
                // Handle *= operator
                else if (std.mem.endsWith(u8, lhs, "*")) {
                    const target = std.mem.trimRight(u8, lhs, "* ");
                    try self.emitCode("MUL {s}, {s}", .{ target, rhs });
                }
                // Handle /= operator
                else if (std.mem.endsWith(u8, lhs, "/")) {
                    const target = std.mem.trimRight(u8, lhs, "/ ");
                    try self.emitCode("DIV {s}, {s}", .{ target, rhs });
                }
                // Handle = assignment
                else {
                    // Check if RHS is a constant or expression
                    if (std.mem.indexOfScalar(u8, rhs, '*')) |mul_idx| {
                        const left = std.mem.trim(u8, rhs[0..mul_idx], " ");
                        const right = std.mem.trim(u8, rhs[mul_idx + 1 ..], " ");
                        try self.emitCode("LDI t0, {s}", .{left});
                        try self.emitCode("LDI t1, {s}", .{right});
                        try self.emitCode("MUL {s}, t0, t1", .{lhs});
                    } else {
                        try self.emitCode("LDI {s}, {s}", .{ lhs, rhs });
                    }
                }
            }
            // Handle return statement
            else if (std.mem.startsWith(u8, trimmed, "return")) {
                const value = std.mem.trim(u8, trimmed["return".len..], " ");
                if (value.len > 0) {
                    try self.emitCode("MOV t0, {s}", .{value});
                }
                try self.emitCode("HALT");
            }
            // Handle for loop: "For i in [0, n):"
            else if (std.mem.startsWith(u8, trimmed, "For")) {
                const loop_end = try self.genLabel("loop_end");
                const loop_body = try self.genLabel("loop_body");

                // Parse: For i in [0, n):
                if (std.mem.indexOf(u8, trimmed, "in [")) |in_idx| {
                    const var_name = std.mem.trim(u8, trimmed["For".len..in_idx], " ");
                    const range_str = trimmed[in_idx + 4 ..];
                    if (std.mem.indexOfScalar(u8, range_str, ',')) |comma_idx| {
                        const start = std.mem.trim(u8, range_str[0..comma_idx], " ");
                        const end_str = range_str[comma_idx + 1 ..];
                        const end = std.mem.trim(u8, end_str, " ):");

                        // Initialize loop variable
                        try self.emitCode("LDI {s}, {s}", .{ var_name, start });

                        // Loop start
                        try self.emitLabel("loop_start");
                        // Check if i >= end
                        try self.emitCode("LDI t1, {s}", .{end});
                        try self.emitCode("SUB t2, {s}, t1", .{var_name});
                        try self.emitCode("JGE t2, {s}", .{loop_end});

                        // Loop body label
                        try self.emitLabel(loop_body);
                    }
                }
            }
            // Handle i++ increment
            else if (std.mem.endsWith(u8, trimmed, "++")) {
                const var_name = std.mem.trimRight(u8, trimmed, "++");
                try self.emitCode("INC {s}", .{var_name});
            }
            // Handle jump/continue
            else if (std.mem.startsWith(u8, trimmed, "continue")) {
                try self.emitCode("JUMP loop_start");
            }
            // Handle conditional jump: "if cond goto label"
            else if (std.mem.startsWith(u8, trimmed, "if")) {
                const rest = std.mem.trim(u8, trimmed["if".len..], " ");
                if (std.mem.indexOf(u8, rest, " goto ")) |goto_idx| {
                    const cond = std.mem.trim(u8, rest[0..goto_idx], " ");
                    const label = std.mem.trim(u8, rest[goto_idx + 6 ..], " ");
                    try self.emitCode("JNZ {s}, {s}", .{ cond, label });
                }
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // UTILITIES
    // ═══════════════════════════════════════════════════════════════════════

    fn getTypeSize(self: *T27Emitter, type_name: []const u8) usize {
        if (std.mem.eql(u8, type_name, "f32")) return 4;
        if (std.mem.eql(u8, type_name, "f64")) return 8;
        if (std.mem.eql(u8, type_name, "u32")) return 4;
        if (std.mem.eql(u8, type_name, "i32")) return 4;
        if (std.mem.eql(u8, type_name, "u16")) return 2;
        if (std.mem.eql(u8, type_name, "i16")) return 2;
        if (std.mem.eql(u8, type_name, "u8")) return 1;
        if (std.mem.eql(u8, type_name, "i8")) return 1;
        if (std.mem.eql(u8, type_name, "bool")) return 1;
        // Handle array types: "[]type"
        if (std.mem.startsWith(u8, type_name, "[]")) {
            const inner = type_name[2..];
            return self.getTypeSize(inner);
        }
        return 4; // default
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FULL FILE GENERATION
    // ═══════════════════════════════════════════════════════════════════════

    pub fn generate(self: *T27Emitter, spec: VibeeSpec, writer: anytype) !void {
        // Header
        try writer.print("; TRI-27 Assembly: Generated from .tri spec\n", .{});
        try writer.print("; {s} v{s}\n", .{ spec.name, spec.version });
        try writer.print("; {s}\n", .{spec.description});
        try writer.print("; φ² + 1/φ² = 3 | TRINITY\n\n", .{});

        // .const section
        if (self.consts.items.len > 0) {
            try writer.writeAll(".const\n");
            try writer.writeAll(self.consts.items);
            try writer.writeAll("\n");
        }

        // .data section
        if (self.data.items.len > 0) {
            try writer.writeAll(".data\n");
            try writer.writeAll(self.data.items);
            try writer.writeAll("\n");
        }

        // .code section
        try writer.writeAll(".code\n");
        try writer.writeAll(self.code.items);
    }

    /// Generate .t27 assembly from VibeeSpec
    pub fn emitSpec(self: *T27Emitter, spec: VibeeSpec, writer: anytype) !void {
        // Emit constants
        try self.emitConsts(spec.constants.items);

        // Emit data section
        try self.emitDataSection(spec);

        // Emit code section
        try self.emitCodeSection(spec);

        // Generate full file
        try self.generate(spec, writer);
    }
};

// ============================================================================
// PARSER INTEGRATION
// ============================================================================

pub const TriParser = struct {
    allocator: Allocator,

    pub fn init(allocator: Allocator) TriParser {
        return .{ .allocator = allocator };
    }

    /// Parse .tri file and return VibeeSpec
    pub fn parseFile(self: *TriParser, path: []const u8) !ParseResult {
        return parseFile(self.allocator, path);
    }

    /// Parse .tri spec from memory
    pub fn parse(self: *TriParser, source: []const u8) !ParseResult {
        return parse(self.allocator, source);
    }
};

// ============================================================================
// MAIN ENTRY POINT
// ============================================================================

pub fn main() !void {
    const allocator = std.heap.page_allocator;

    const args = try std.process.argsAlloc(allocator);
    defer std.process.argsFree(allocator, args);

    if (args.len < 2) {
        std.debug.print("Usage: {s} <input.tri> [output.t27]\n", .{args[0]});
        std.debug.print("\nemit_t27: .tri spec → .t27 assembly code generator\n", .{});
        std.debug.print("Part of VIBEE compiler pipeline\n", .{});
        std.debug.print("φ² + 1/φ² = 3 | TRINITY\n", .{});
        return;
    }

    const input_path = args[1];
    const output_path = if (args.len >= 3) args[2] else try std.fmt.allocPrint(allocator, "{s}.t27", .{std.fs.path.stem(input_path)});
    defer if (args.len < 3) allocator.free(output_path);

    // Parse input
    var parser = TriParser.init(allocator);
    const parse_result = try parser.parseFile(input_path);
    defer parse_result.deinit(allocator);

    if (parse_result.hasErrors()) {
        std.debug.print("Parse errors:\n", .{});
        for (parse_result.errors.items) |err| {
            std.debug.print("  - {s}\n", .{err});
        }
        return error.ParseFailed;
    }

    // Generate .t27 assembly
    var emitter = T27Emitter.init(allocator);
    defer emitter.deinit();

    const out_file = try std.fs.cwd().createFile(output_path, .{});
    defer out_file.close();

    const writer = out_file.writer();
    try emitter.emitSpec(parse_result.spec, writer);

    std.debug.print("Generated: {s}\n", .{output_path});
}

// ============================================================================
// TESTS
// ============================================================================

test "T27Emitter: basic init/deinit" {
    const allocator = std.testing.allocator;
    var emitter = T27Emitter.init(allocator);
    defer emitter.deinit(allocator);

    try std.testing.expectEqual(@as(usize, 0), emitter.label_counter);
}

test "T27Emitter: emitConst" {
    const allocator = std.testing.allocator;
    var emitter = T27Emitter.init(allocator);
    defer emitter.deinit(allocator);

    const const_val: Constant = .{
        .name = "TEST_CONST",
        .value = 42,
        .string_value = "",
        .is_string = false,
        .description = "Test constant",
    };

    try emitter.emitConsts(&[_]Constant{const_val});
    try std.testing.expect(emitter.consts.items.len > 0);
}

test "T27Emitter: getTypeSize" {
    const allocator = std.testing.allocator;
    var emitter = T27Emitter.init(allocator);
    defer emitter.deinit(allocator);

    try std.testing.expectEqual(@as(usize, 4), emitter.getTypeSize("f32"));
    try std.testing.expectEqual(@as(usize, 8), emitter.getTypeSize("f64"));
    try std.testing.expectEqual(@as(usize, 1), emitter.getTypeSize("bool"));
    try std.testing.expectEqual(@as(usize, 4), emitter.getTypeSize("unknown"));
}

test "TriParser: parse simple spec" {
    const allocator = std.testing.allocator;
    const source =
        \\name: test_module
        \\version: "1.0.0"
        \\language: zig
        \\module: test.module
        \\description: "Test module"
    ;

    var parser = TriParser.init(allocator);
    const result = try parser.parse(source);
    defer result.deinit(allocator);

    try std.testing.expect(result.success());
    try std.testing.expectEqualStrings("test_module", result.spec.name);
}

test "emit_t27: full pipeline" {
    const allocator = std.testing.allocator;
    const source =
        \\name: adder
        \\version: "1.0.0"
        \\language: zig
        \\module: test.adder
        \\description: "Simple adder"
        \\behaviors:
        \\  - name: add_two_numbers
        \\    description: "Add a and b"
        \\    implementation: |
        \\      result = a + b
        \\      return result
    ;

    var parser = TriParser.init(allocator);
    const parse_result = try parser.parse(source);
    defer parse_result.deinit(allocator);

    try std.testing.expect(parse_result.success());

    var emitter = T27Emitter.init(allocator);
    defer emitter.deinit(allocator);

    var buffer = ArrayList(u8){};
    defer buffer.deinit(allocator);

    {
        const writer = buffer.writer(allocator);
        try emitter.emitSpec(parse_result.spec, writer);
    }

    try std.testing.expect(buffer.items.len > 0);

    // Check that output contains expected sections
    const output = buffer.items;
    try std.testing.expect(std.mem.indexOf(u8, output, ".code") != null);
    try std.testing.expect(std.mem.indexOf(u8, output, "HALT") != null);
}
