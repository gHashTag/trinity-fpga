// emit_t27: .tri spec → .t27 assembly code generator
// Part of VIBEE compiler pipeline
// φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const Allocator = std.mem.Allocator;
const ArrayList = std.ArrayListUnmanaged;

// Parser types
const Constant = @import("gen_parser_types.zig").Constant;
const TypeDef = @import("gen_parser_types.zig").TypeDef;
const Field = @import("gen_parser_types.zig").Field;
const Behavior = @import("gen_parser_types.zig").Behavior;
const TestCase = @import("gen_parser_types.zig").TestCase;

// ============================================================================
// TRI-27 ASSEMBLY SPECIFICATION
// ============================================================================

// .t27 assembly format specification:
// - .const section: constant definitions
// - .data section: data labels (.word, .dword, .ascii)
// - .code section: instructions
//
// Instructions (Coptic alphabet registers t0-t26):
//   LDI  dst, imm   - Load immediate
//   LD   dst, src   - Load from memory
//   ST   dst, src   - Store to memory
//   MOV  dst, src   - Move register
//   ADD  dst, src   - Add
//   SUB  dst, src   - Subtract
//   MUL  dst, src   - Multiply
//   DIV  dst, src   - Divide
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

    pub fn init(allocator: Allocator) T27Emitter {
        return .{
            .allocator = allocator,
            .code = ArrayList(u8).init(allocator),
            .data = ArrayList(u8).init(allocator),
            .consts = ArrayList(u8).init(allocator),
        };
    }

    pub fn deinit(self: *T27Emitter) void {
        self.code.deinit(self.allocator);
        self.data.deinit(self.allocator);
        self.consts.deinit(self.allocator);
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // SECTION HELPERS
    // ═══════════════════════════════════════════════════════════════════════════════

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

    // ═══════════════════════════════════════════════════════════════════════════════
    // .CONST SECTION GENERATION
    // ═══════════════════════════════════════════════════════════════════════════════

    pub fn emitConsts(self: *T27Emitter, constants: []const Constant) !void {
        if (constants.len == 0) return;

        try self.emitConst(";");
        try self.emitConst(" TRI-27 Constants");
        try self.emitConst("");

        for (constants) |c| {
            if (c.is_string) {
                try self.emitConst("{s}: .ascii \"{s}\"", .{ c.name, c.string_value });
            } else {
                try self.emitConst("{s}: .double {d:.6}", .{ c.name, c.value });
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // .DATA SECTION GENERATION
    // ═══════════════════════════════════════════════════════════════════════════════

    pub fn emitData(self: *T27Emitter, type_def: TypeDef) !void {
        try self.emitData(";");
        try self.emitData(" Data section for {s}", .{type_def.name});
        try self.emitData("");

        // Emit fields as data labels
        for (type_def.fields.items) |f| {
            const type_size = self.getTypeSize(f.type_name);
            try self.emitData("{s}: .skip {}", .{ f.name, type_size });
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // .CODE SECTION GENERATION
    // ═══════════════════════════════════════════════════════════════════════════════

    pub fn emitFunction(self: *T27Emitter, behavior: Behavior, type_def: TypeDef) !void {
        try self.emitCode(";");
        try self.emitCode(" {s} - {s}", .{ behavior.name, type_def.name });
        try self.emitCode(";");
        try self.emitCode("");

        // Parse formula and generate instructions
        try self.emitFormula(behavior.implementation, type_def);
    }

    fn emitFormula(self: *T27Emitter, formula: []const u8, type_def: TypeDef) !void {
        // For now, emit a simple placeholder
        _ = type_def;

        try self.emitCode(" ; Formula: {s}", .{formula});
        try self.emitCode(" ; TODO: Parse and compile to T27 instructions");
        try self.emitCode(" HALT");
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // UTILITIES
    // ═══════════════════════════════════════════════════════════════════════════════

    fn getTypeSize(self: *T27Emitter, type_name: []const u8) usize {
        if (std.mem.eql(u8, type_name, "f32")) return 4;
        if (std.mem.eql(u8, type_name, "f64")) return 8;
        if (std.mem.eql(u8, type_name, "u32")) return 4;
        if (std.mem.eql(u8, type_name, "i32")) return 4;
        if (std.mem.eql(u8, type_name, "bool")) return 1;
        return 4; // default
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // FULL FILE GENERATION
    // ═══════════════════════════════════════════════════════════════════════════════

    pub fn generate(self: *T27Emitter, spec: anytype, writer: anytype) !void {
        _ = spec;

        // Header
        try writer.print("; TRI-27 Assembly: Generated from .tri spec\n", .{});
        try writer.print("; φ² + 1/φ² = 3 | TRINITY\n\n", .{});

        // .const section
        if (self.consts.items.len > 0) {
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
};

// ============================================================================
// PARSER INTEGRATION
// ============================================================================

pub const TriParser = struct {
    allocator: Allocator,

    pub fn init(allocator: Allocator) TriParser {
        return .{ .allocator = allocator };
    }

    /// Parse .tri file and return Algorithm AST
    pub fn parseFile(self: *TriParser, path: []const u8) !Algorithm {
        const source = try std.fs.cwd().readFileAlloc(self.allocator, path, self.allocator);
        defer self.allocator.free(source);

        return try self.parse(source);
    }

    /// Parse .tri spec from memory
    pub fn parse(self: *TriParser, source: []const u8) !Algorithm {
        _ = source;
        // TODO: Implement full YAML parser
        return error.NotImplemented;
    }
};

// ============================================================================
// ALGORITHM TYPE (from parser_types.zig)
// ============================================================================

pub const Algorithm = struct {
    name: []const u8,
    version: []const u8,
    module: []const u8,
    description: []const u8,
    types: ArrayList(TypeDef),
    constants: ArrayList(Constant),
    functions: ArrayList(Behavior),

    pub fn init(allocator: Allocator) Algorithm {
        return .{
            .name = "",
            .version = "",
            .module = "",
            .description = "",
            .types = ArrayList(TypeDef).init(allocator),
            .constants = ArrayList(Constant).init(allocator),
            .functions = ArrayList(Behavior).init(allocator),
        };
    }

    pub fn deinit(self: *Algorithm, allocator: Allocator) void {
        self.types.deinit(allocator);
        self.constants.deinit(allocator);
        self.functions.deinit(allocator);
    }
};
