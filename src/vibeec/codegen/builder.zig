// ═══════════════════════════════════════════════════════════════════════════════
// CODE BUILDER - Buffer management and output generation
// ═══════════════════════════════════════════════════════════════════════════════
//
// φ² + 1/φ² = 3
//
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");
const Allocator = std.mem.Allocator;

pub const CodeBuilder = struct {
    allocator: Allocator,
    buffer: std.ArrayListUnmanaged(u8),
    indent: u32,

    const Self = @This();

    pub fn init(allocator: Allocator) Self {
        return Self{
            .allocator = allocator,
            .buffer = .empty,
            .indent = 0,
        };
    }

    pub fn deinit(self: *Self) void {
        self.buffer.deinit(self.allocator);
    }

    pub fn write(self: *Self, str: []const u8) !void {
        try self.buffer.appendSlice(self.allocator, str);
    }

    pub fn writeByte(self: *Self, byte: u8) !void {
        try self.buffer.append(self.allocator, byte);
    }

    /// Write `// <label><value>` as a comment, giving EVERY line of a
    /// multi-line value its own `//` marker.
    ///
    /// Spec values are routinely multi-line -- `then: |` block scalars are the
    /// normal way to write a numbered list -- and `writeFmt("// X: {s}\n", ...)`
    /// marks only the first line. The rest landed in the generated file as
    /// bare code and it did not parse: `expected ';' after statement` was the
    /// most common first error in generated output, and this was one of its
    /// two causes.
    ///
    /// `marker` is "//" or "///" so the doc-comment path can share this.
    pub fn writeCommentLines(self: *Self, marker: []const u8, label: []const u8, value: []const u8) !void {
        if (value.len == 0) {
            try self.writeIndent();
            try self.buffer.appendSlice(self.allocator, marker);
            try self.buffer.append(self.allocator, ' ');
            try self.buffer.appendSlice(self.allocator, label);
            try self.buffer.append(self.allocator, '\n');
            return;
        }
        var first = true;
        var it = std.mem.splitScalar(u8, value, '\n');
        while (it.next()) |line| {
            const trimmed = std.mem.trim(u8, line, " \t\r");
            try self.writeIndent();
            try self.buffer.appendSlice(self.allocator, marker);
            try self.buffer.append(self.allocator, ' ');
            if (first) {
                try self.buffer.appendSlice(self.allocator, label);
                first = false;
            }
            try self.buffer.appendSlice(self.allocator, trimmed);
            try self.buffer.append(self.allocator, '\n');
        }
    }

    pub fn writeLine(self: *Self, str: []const u8) !void {
        try self.writeIndent();
        try self.buffer.appendSlice(self.allocator, str);
        try self.buffer.append(self.allocator, '\n');
    }

    pub fn writeIndent(self: *Self) !void {
        var i: u32 = 0;
        while (i < self.indent) : (i += 1) {
            try self.buffer.appendSlice(self.allocator, "    ");
        }
    }

    pub fn writeFmt(self: *Self, comptime fmt: []const u8, args: anytype) !void {
        // 0.16 removed ArrayList.writer(); the list prints directly.
        try self.buffer.print(self.allocator, fmt, args);
    }

    pub fn newline(self: *Self) !void {
        try self.buffer.append(self.allocator, '\n');
    }

    pub fn incIndent(self: *Self) void {
        self.indent += 1;
    }

    pub fn decIndent(self: *Self) void {
        if (self.indent > 0) self.indent -= 1;
    }

    pub fn getOutput(self: *Self) []const u8 {
        return self.buffer.items;
    }

    pub fn toOwnedSlice(self: *Self) ![]u8 {
        const result = try self.buffer.toOwnedSlice(self.allocator);
        return result;
    }
};
