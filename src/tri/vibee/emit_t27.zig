// emit_t27: .tri spec → .t27 assembly code generator
// Part of VIBEE compiler pipeline
// φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const Allocator = std.mem.Allocator;
const ArrayList = std.ArrayListUnmanaged;

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
            .code = .{},
            .data = .{},
            .consts = .{},
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
        try self.consts.appendSlice(self.allocator, line);
        try self.consts.append(self.allocator, '\n');
    }

    fn emitConstLine(self: *T27Emitter, line: []const u8) !void {
        try self.consts.appendSlice(self.allocator, line);
        try self.consts.append(self.allocator, '\n');
    }

    fn emitData(self: *T27Emitter, comptime fmt: []const u8, args: anytype) !void {
        const line = try std.fmt.allocPrint(self.allocator, fmt, args);
        defer self.allocator.free(line);
        try self.data.appendSlice(self.allocator, line);
        try self.data.append(self.allocator, '\n');
    }

    fn emitDataLine(self: *T27Emitter, line: []const u8) !void {
        try self.data.appendSlice(self.allocator, line);
        try self.data.append(self.allocator, '\n');
    }

    fn emitCode(self: *T27Emitter, comptime fmt: []const u8, args: anytype) !void {
        const line = try std.fmt.allocPrint(self.allocator, fmt, args);
        defer self.allocator.free(line);
        try self.code.appendSlice(self.allocator, line);
        try self.code.append(self.allocator, '\n');
    }

    fn emitCodeLine(self: *T27Emitter, line: []const u8) !void {
        try self.code.appendSlice(self.allocator, line);
        try self.code.append(self.allocator, '\n');
    }

    fn emitComment(self: *T27Emitter, comptime fmt: []const u8, args: anytype) !void {
        const line = try std.fmt.allocPrint(self.allocator, "; " ++ fmt, args);
        defer self.allocator.free(line);
        try self.code.appendSlice(self.allocator, line);
        try self.code.append(self.allocator, '\n');
    }

    fn emitCommentLine(self: *T27Emitter, line: []const u8) !void {
        try self.code.appendSlice(self.allocator, line);
        try self.code.append(self.allocator, '\n');
    }

    fn emitLabel(self: *T27Emitter, name: []const u8) !void {
        const line = try std.fmt.allocPrint(self.allocator, "{s}:", .{name});
        defer self.allocator.free(line);
        try self.code.appendSlice(self.allocator, line);
        try self.code.append(self.allocator, '\n');
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

        try self.emitConstLine("; TRI-27 Constants");
        try self.emitConstLine("; φ² + 1/φ² = 3 | TRINITY");

        for (constants) |c| {
            if (c.is_string) {
                try self.emitConst("{s}: .ascii \"{s}\"", .{ c.name, c.string_value });
            } else {
                const int_val: i64 = @intFromFloat(c.value);
                try self.emitConst("{s} = {d}", .{ c.name, int_val });
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // .DATA SECTION GENERATION
    // ═══════════════════════════════════════════════════════════════════════

    pub fn emitDataSection(self: *T27Emitter, spec: TriSpec) !void {
        try self.emitDataLine("; Data section");
        try self.emitData("; Generated from {s}", .{spec.name});

        for (spec.types.items) |t| {
            try self.emitDataLine("");
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

    pub fn emitCodeSection(self: *T27Emitter, spec: TriSpec) !void {
        try self.emitCodeLine("; Code section");
        try self.emitCode("; Generated from {s} v{s}", .{ spec.name, spec.version });
        try self.emitCodeLine("; φ² + 1/φ² = 3 | TRINITY");
        try self.emitCodeLine("");

        try self.emitLabel("main");
        try self.emitComment("Entry point for {s}", .{spec.name});

        for (spec.behaviors.items) |b| {
            try self.emitBehavior(b);
        }

        try self.emitCodeLine("");
        try self.emitCodeLine("HALT");
    }

    fn emitBehavior(self: *T27Emitter, behavior: Behavior) !void {
        try self.emitCodeLine("");
        try self.emitLabel(behavior.name);
        try self.emitComment("{s}", .{behavior.description});

        if (behavior.implementation.len > 0) {
            try self.emitFormula(behavior.implementation);
        } else {
            try self.emitComment("; TODO: implement {s}", .{behavior.name});
            try self.emitCodeLine("HALT");
        }
    }

    fn emitFormula(self: *T27Emitter, formula: []const u8) !void {
        var lines = std.mem.splitScalar(u8, formula, '\n');
        while (lines.next()) |line| {
            const trimmed = std.mem.trim(u8, line, " \t\r");
            if (trimmed.len == 0) continue;
            if (trimmed[0] == '#') continue;

            // Handle basic patterns
            if (std.mem.indexOfScalar(u8, trimmed, '=')) |eq_idx| {
                const lhs = std.mem.trim(u8, trimmed[0..eq_idx], " ");
                var rhs = std.mem.trim(u8, trimmed[eq_idx + 1 ..], " ");

                // += operator
                if (std.mem.endsWith(u8, lhs, "+")) {
                    const target = std.mem.trimRight(u8, lhs, "+ ");
                    try self.emitCode("ADD {s}, {s}", .{ target, rhs });
                }
                // -= operator
                else if (std.mem.endsWith(u8, lhs, "-")) {
                    const target = std.mem.trimRight(u8, lhs, "- ");
                    try self.emitCode("SUB {s}, {s}", .{ target, rhs });
                }
                // *= operator
                else if (std.mem.endsWith(u8, lhs, "*")) {
                    const target = std.mem.trimRight(u8, lhs, "* ");
                    try self.emitCode("MUL {s}, {s}", .{ target, rhs });
                }
                // /= operator
                else if (std.mem.endsWith(u8, lhs, "/")) {
                    const target = std.mem.trimRight(u8, lhs, "/ ");
                    try self.emitCode("DIV {s}, {s}", .{ target, rhs });
                }
                // = assignment
                else {
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
            // return statement
            else if (std.mem.startsWith(u8, trimmed, "return")) {
                const value = std.mem.trim(u8, trimmed["return".len..], " ");
                if (value.len > 0) {
                    try self.emitCode("MOV t0, {s}", .{value});
                }
                try self.emitCodeLine("HALT");
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
        if (std.mem.startsWith(u8, type_name, "[]")) {
            const inner = type_name[2..];
            return self.getTypeSize(inner);
        }
        return 4;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FULL FILE GENERATION
    // ═══════════════════════════════════════════════════════════════════════

    pub fn generate(self: *T27Emitter, spec: TriSpec, file: std.fs.File) !void {
        try file.writeAll("; TRI-27 Assembly: Generated from .tri spec\n");
        const line1 = try std.fmt.allocPrint(self.allocator, "; {s} v{s}\n", .{ spec.name, spec.version });
        defer self.allocator.free(line1);
        try file.writeAll(line1);
        const line2 = try std.fmt.allocPrint(self.allocator, "; {s}\n", .{spec.description});
        defer self.allocator.free(line2);
        try file.writeAll(line2);
        try file.writeAll("; φ² + 1/φ² = 3 | TRINITY\n\n");

        if (self.consts.items.len > 0) {
            try file.writeAll(".const\n");
            try file.writeAll(self.consts.items);
            try file.writeAll("\n");
        }

        if (self.data.items.len > 0) {
            try file.writeAll(".data\n");
            try file.writeAll(self.data.items);
            try file.writeAll("\n");
        }

        try file.writeAll(".code\n");
        try file.writeAll(self.code.items);
    }

    pub fn emitSpec(self: *T27Emitter, spec: TriSpec, file: std.fs.File) !void {
        try self.emitConsts(spec.constants.items);
        try self.emitDataSection(spec);
        try self.emitCodeSection(spec);
        try self.generate(spec, file);
    }
};

// ============================================================================
// ALGO TRI SPEC AST TYPES
// ============================================================================

// Type expression: f32, []f32, ReLUConfig, etc.
pub const AstTypeExpr = union(enum) {
    base: []const u8, // f32, i32, bool, etc.
    slice_const: struct { // []const T
        inner: []const u8,
    },
    slice_mut: struct { // []T
        inner: []const u8,
    },
    named: []const u8, // Named type like ReLUConfig
};

// Function parameter: name, type, description
pub const AstParam = struct {
    name: []const u8,
    type: AstTypeExpr,
    description: []const u8,
};

// Type declaration with fields
pub const AstField = struct {
    name: []const u8,
    type: AstTypeExpr,
    description: []const u8,
};

pub const AstTypeDecl = struct {
    name: []const u8,
    description: []const u8,
    fields: ArrayList(AstField),

    pub fn deinit(self: *AstTypeDecl, allocator: Allocator) void {
        if (self.name.len > 0) allocator.free(self.name);
        if (self.description.len > 0) allocator.free(self.description);
        for (self.fields.items) |*f| {
            if (f.name.len > 0) allocator.free(f.name);
            if (f.description.len > 0) allocator.free(f.description);
        }
        self.fields.deinit(allocator);
    }
};

// Constant declaration: name, type, value
pub const AstConstDecl = struct {
    name: []const u8,
    type: AstTypeExpr,
    value: f64,
    string_value: []const u8,
    description: []const u8,

    pub fn deinit(self: *AstConstDecl, allocator: Allocator) void {
        if (self.name.len > 0) allocator.free(self.name);
        if (self.description.len > 0) allocator.free(self.description);
        if (self.string_value.len > 0) allocator.free(self.string_value);
    }
};

// Function declaration with parameters, returns, formula
pub const AstFuncDecl = struct {
    name: []const u8,
    params: ArrayList(AstParam),
    returns: AstTypeExpr,
    description: []const u8,
    formula: []const u8,

    pub fn deinit(self: *AstFuncDecl, allocator: Allocator) void {
        if (self.name.len > 0) allocator.free(self.name);
        if (self.description.len > 0) allocator.free(self.description);
        if (self.formula.len > 0) allocator.free(self.formula);
        for (self.params.items) |*p| {
            if (p.name.len > 0) allocator.free(p.name);
            if (p.description.len > 0) allocator.free(p.description);
        }
        self.params.deinit(allocator);
    }
};

// Behavior entry with meta-info (no Zig code)
pub const AstBehavior = struct {
    name: []const u8,
    description: []const u8,
    notes: []const u8, // Replaces 'implementation' with cleaner name

    pub fn deinit(self: *AstBehavior, allocator: Allocator) void {
        if (self.name.len > 0) allocator.free(self.name);
        if (self.description.len > 0) allocator.free(self.description);
        if (self.notes.len > 0) allocator.free(self.notes);
    }
};

// ============================================================================
// LEGACY SIMPLE TRI SPEC TYPES (backward compat)
// ============================================================================

pub const Constant = struct {
    name: []const u8,
    value: f64,
    string_value: []const u8,
    is_string: bool,
    description: []const u8,
};

pub const Field = struct {
    name: []const u8,
    type_name: []const u8,
    description: []const u8,
};

pub const TypeDef = struct {
    name: []const u8,
    description: []const u8,
    fields: ArrayList(Field),
};

pub const Behavior = struct {
    name: []const u8,
    description: []const u8,
    implementation: []const u8,
};

pub const TriSpec = struct {
    name: []const u8,
    version: []const u8,
    module: []const u8,
    description: []const u8,
    types: ArrayList(TypeDef), // Legacy
    constants: ArrayList(Constant), // Legacy
    behaviors: ArrayList(Behavior), // Legacy

    // ALGO-DSL parsed structures
    type_decls: ArrayList(AstTypeDecl),
    const_decls: ArrayList(AstConstDecl),
    func_decls: ArrayList(AstFuncDecl),
    behavior_decls: ArrayList(AstBehavior),

    const DEFAULT_VERSION: []const u8 = "1.0.0";

    pub fn init(_: Allocator) TriSpec {
        return .{
            .name = "",
            .version = DEFAULT_VERSION,
            .module = "",
            .description = "",
            .types = .{},
            .constants = .{},
            .behaviors = .{},
            .type_decls = .{},
            .const_decls = .{},
            .func_decls = .{},
            .behavior_decls = .{},
        };
    }

    pub fn deinit(self: *TriSpec, allocator: Allocator) void {
        // parse() always allocates these, so always free if non-empty
        if (self.name.len > 0) allocator.free(self.name);
        if (self.version.len > 0) allocator.free(self.version);
        if (self.module.len > 0) allocator.free(self.module);
        if (self.description.len > 0) allocator.free(self.description);

        // Legacy cleanup
        for (self.types.items) |*t| {
            t.fields.deinit(allocator);
        }
        self.types.deinit(allocator);
        self.constants.deinit(allocator);
        self.behaviors.deinit(allocator);

        // ALGO-DSL cleanup
        for (self.type_decls.items) |*t| {
            t.deinit(allocator);
        }
        for (self.const_decls.items) |*c| {
            c.deinit(allocator);
        }
        for (self.func_decls.items) |*f| {
            f.deinit(allocator);
        }
        for (self.behavior_decls.items) |*b| {
            b.deinit(allocator);
        }
        self.type_decls.deinit(allocator);
        self.const_decls.deinit(allocator);
        self.func_decls.deinit(allocator);
        self.behavior_decls.deinit(allocator);
    }
};

// ============================================================================
// SIMPLE TRI PARSER
// ============================================================================

pub const TriParser = struct {
    allocator: Allocator,

    pub fn init(allocator: Allocator) TriParser {
        return .{ .allocator = allocator };
    }

    pub fn parse(self: *TriParser, source: []const u8) !TriSpec {
        var spec = TriSpec.init(self.allocator);
        errdefer spec.deinit(self.allocator);

        var lines = std.mem.splitScalar(u8, source, '\n');
        var current_section: enum { none, header, types, constants, behaviors } = .none;

        while (lines.next()) |line| {
            const trimmed = std.mem.trim(u8, line, " \t\r");
            if (trimmed.len == 0) continue;
            if (trimmed[0] == '#') continue;

            if (std.mem.indexOfScalar(u8, trimmed, ':')) |colon_idx| {
                const key = std.mem.trim(u8, trimmed[0..colon_idx], " ");
                var value = std.mem.trim(u8, trimmed[colon_idx + 1 ..], " ");

                // Remove quotes if present
                if (value.len >= 2 and value[0] == '"') {
                    value = value[1 .. value.len - 1];
                }

                // Identify section
                if (std.mem.eql(u8, key, "name")) {
                    spec.name = try self.allocator.dupe(u8, value);
                } else if (std.mem.eql(u8, key, "version")) {
                    spec.version = try self.allocator.dupe(u8, value);
                } else if (std.mem.eql(u8, key, "module")) {
                    spec.module = try self.allocator.dupe(u8, value);
                } else if (std.mem.eql(u8, key, "description")) {
                    spec.description = try self.allocator.dupe(u8, value);
                } else if (std.mem.eql(u8, key, "types")) {
                    current_section = .types;
                } else if (std.mem.eql(u8, key, "constants")) {
                    current_section = .constants;
                } else if (std.mem.eql(u8, key, "behaviors") or std.mem.eql(u8, key, "functions")) {
                    current_section = .behaviors;
                }
            }
        }

        return spec;
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
    const source = try std.fs.cwd().readFileAlloc(allocator, input_path, 1024 * 1024);
    defer allocator.free(source);

    var parser = TriParser.init(allocator);
    var spec = try parser.parse(source);
    defer spec.deinit(allocator);

    // Generate .t27 assembly
    var emitter = T27Emitter.init(allocator);
    defer emitter.deinit();

    const out_file = try std.fs.cwd().createFile(output_path, .{});
    defer out_file.close();

    try emitter.emitSpec(spec, out_file);

    std.debug.print("Generated: {s}\n", .{output_path});
}

// ============================================================================
// TESTS
// ============================================================================

test "T27Emitter: basic init/deinit" {
    const allocator = std.testing.allocator;
    var emitter = T27Emitter.init(allocator);
    defer emitter.deinit();

    try std.testing.expectEqual(@as(usize, 0), emitter.label_counter);
}

test "T27Emitter: getTypeSize" {
    const allocator = std.testing.allocator;
    var emitter = T27Emitter.init(allocator);
    defer emitter.deinit();

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
        \\module: test.module
        \\description: "Test module"
    ;

    var parser = TriParser.init(allocator);
    var spec = try parser.parse(source);
    defer spec.deinit(allocator);

    try std.testing.expectEqualStrings("test_module", spec.name);
    try std.testing.expectEqualStrings("1.0.0", spec.version);
}

test "emit_t27: full pipeline" {
    const allocator = std.testing.allocator;
    const source =
        \\name: adder
        \\version: "1.0.0"
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
    var spec = try parser.parse(source);
    defer spec.deinit(allocator);

    try std.testing.expectEqualStrings("adder", spec.name);

    var emitter = T27Emitter.init(allocator);
    defer emitter.deinit();

    // Generate the spec (using emitConsts/emitDataSection/emitCodeSection directly)
    try emitter.emitConsts(spec.constants.items);
    try emitter.emitDataSection(spec);
    try emitter.emitCodeSection(spec);

    try std.testing.expect(emitter.code.items.len > 0);
    try std.testing.expect(std.mem.indexOf(u8, emitter.code.items, "HALT") != null);
}
