//! VIBEE Parser — Generated from specs/vibee/vibee_parser.tri
//! φ² + 1/φ² = 3 | TRINITY
//!
//! DO NOT EDIT: This file is generated from vibee_parser.tri spec
//!
//! Simple YAML-based parser for .tri specification files

const std = @import("std");
const tri_io = @import("tri_io");
const Allocator = std.mem.Allocator;
const ArrayList = std.ArrayListUnmanaged;

pub const parser_types = @import("gen_parser_types.zig");

// Re-export key types
pub const VibeeSpec = parser_types.VibeeSpec;
pub const TypeDef = parser_types.TypeDef;
pub const Behavior = parser_types.Behavior;
pub const Field = parser_types.Field;
pub const TestCase = parser_types.TestCase;

// ============================================================================
// PARSE RESULT
// ============================================================================

/// Result of parsing operation
///
/// Ownership, because it is not obvious and it is load-bearing:
///
///   * `spec`'s seven header strings (name/version/language/module/description/
///     author/license) are owned by `allocator`, because `VibeeSpec.deinit`
///     frees exactly those with the allocator handed to it. A header value that
///     equals the field's default literal ("1.0.0", "zig", "MIT", "") is stored
///     as that literal and NOT duplicated -- `VibeeSpec.deinit` skips those, so
///     duplicating them would leak.
///   * Every string reachable through `spec`'s collections (TypeDef, Field,
///     Behavior, Constant, Import, TestCase) is owned by `strings`, the arena
///     below. `gen_parser_types.zig` frees the *ArrayLists* but never the
///     strings inside them, so the arena is what makes them free-able without
///     editing that file.
///   * The ArrayLists themselves (and errors/warnings) are owned by
///     `allocator`, because that is what their deinit is called with.
///
/// Nothing points into the `source` buffer passed to `parse`.
pub const ParseResult = struct {
    spec: VibeeSpec,
    errors: ArrayList([]const u8),
    warnings: ArrayList([]const u8),
    /// Backing store for every string inside `spec`'s collections.
    strings: std.heap.ArenaAllocator,

    pub fn init(allocator: Allocator) ParseResult {
        return .{
            .spec = VibeeSpec.init(allocator),
            .errors = .empty,
            .warnings = .empty,
            .strings = std.heap.ArenaAllocator.init(allocator),
        };
    }

    pub fn deinit(self: *ParseResult, allocator: Allocator) void {
        self.spec.deinit(allocator);
        for (self.errors.items) |err| allocator.free(err);
        self.errors.deinit(allocator);
        for (self.warnings.items) |warn| allocator.free(warn);
        self.warnings.deinit(allocator);
        self.strings.deinit();
    }

    pub fn hasErrors(self: *const ParseResult) bool {
        return self.errors.items.len > 0;
    }

    pub fn success(self: *const ParseResult) bool {
        return self.errors.items.len == 0;
    }
};

// ============================================================================
// YAML PARSING HELPERS
// ============================================================================

/// Parse a key-value pair from YAML line
/// Returns: key, value, new_position
pub fn parseKeyValue(line: []const u8) struct { []const u8, []const u8, bool } {
    const colon_idx = std.mem.indexOfScalar(u8, line, ':') orelse return .{ "", "", false };

    const key = std.mem.trim(u8, line[0..colon_idx], " \t");
    var value: []const u8 = "";

    if (colon_idx + 1 < line.len) {
        value = std.mem.trim(u8, line[colon_idx + 1 ..], " \t\r\n");
    }

    // Handle quoted strings
    if (value.len >= 2 and ((value[0] == '"' and value[value.len - 1] == '"') or (value[0] == '\'' and value[value.len - 1] == '\''))) {
        value = value[1 .. value.len - 1];
    }

    return .{ key, value, true };
}

/// Check if line is a comment
pub fn isComment(line: []const u8) bool {
    const trimmed = std.mem.trimStart(u8, line, " \t");
    return trimmed.len > 0 and trimmed[0] == '#';
}

/// Check if line is empty (whitespace only)
pub fn isEmptyLine(line: []const u8) bool {
    return std.mem.trim(u8, line, " \t\r\n").len == 0;
}

/// Get indentation level (number of leading spaces)
pub fn getIndentLevel(line: []const u8) usize {
    var level: usize = 0;
    for (line) |c| {
        if (c == ' ') level += 1 else break;
    }
    return level / 2; // Assuming 2-space indentation
}

/// Check if line starts a list item (-)
pub fn isListItem(line: []const u8) bool {
    const trimmed = std.mem.trimStart(u8, line, " \t");
    return trimmed.len > 0 and trimmed[0] == '-';
}

/// Extract list item value after '-'
pub fn extractListItem(line: []const u8) []const u8 {
    const trimmed = std.mem.trimStart(u8, line, " \t");
    if (trimmed.len > 0 and trimmed[0] == '-') {
        const rest = std.mem.trimStart(u8, trimmed[1..], " \t");
        // Remove quotes if present
        if (rest.len >= 2 and ((rest[0] == '"' and rest[rest.len - 1] == '"') or (rest[0] == '\'' and rest[rest.len - 1] == '\''))) {
            return rest[1 .. rest.len - 1];
        }
        return std.mem.trim(u8, rest, " \t\r\n");
    }
    return "";
}

/// Strip a trailing `# comment` from a line.
///
/// YAML only treats `#` as a comment when it starts the line or follows
/// whitespace, and never inside a quoted scalar. Both matter here: the corpus
/// has 2637 lines with a trailing comment (`- scope: RefactorScope   # ...`)
/// and values such as `"phi^2 + 1/phi^2 = 3"` that must survive intact.
/// Returns a slice of `line`; never allocates.
pub fn stripInlineComment(line: []const u8) []const u8 {
    var in_single = false;
    var in_double = false;
    var i: usize = 0;
    while (i < line.len) : (i += 1) {
        const c = line[i];
        if (c == '"' and !in_single) {
            in_double = !in_double;
        } else if (c == '\'' and !in_double) {
            in_single = !in_single;
        } else if (c == '#' and !in_single and !in_double) {
            if (i == 0 or line[i - 1] == ' ' or line[i - 1] == '\t') {
                return std.mem.trimEnd(u8, line[0..i], " \t\r");
            }
        }
    }
    return std.mem.trimEnd(u8, line, " \t\r");
}

/// True for a YAML block-scalar introducer (`description: |`).
/// 560 specs open their top-level `description` this way.
pub fn isBlockScalar(value: []const u8) bool {
    return std.mem.eql(u8, value, "|") or
        std.mem.eql(u8, value, ">") or
        std.mem.eql(u8, value, "|-") or
        std.mem.eql(u8, value, ">-") or
        std.mem.eql(u8, value, "|+") or
        std.mem.eql(u8, value, ">+");
}

/// If `body` (already left-trimmed) is a list item, return its content,
/// otherwise null. `-` must be followed by whitespace or end-of-line so that
/// a negative number is not mistaken for a bullet.
pub fn listItemBody(body: []const u8) ?[]const u8 {
    if (body.len == 0 or body[0] != '-') return null;
    if (body.len == 1) return "";
    if (body[1] != ' ' and body[1] != '\t') return null;
    return std.mem.trim(u8, body[2..], " \t\r");
}

/// Remove one layer of matching surrounding quotes.
pub fn unquote(value: []const u8) []const u8 {
    if (value.len >= 2 and
        ((value[0] == '"' and value[value.len - 1] == '"') or
            (value[0] == '\'' and value[value.len - 1] == '\'')))
    {
        return value[1 .. value.len - 1];
    }
    return value;
}

// ============================================================================
// SECTION PARSING
// ============================================================================

const Section = enum {
    none,
    header,
    types,
    behaviors,
    constants,
    functions,
    algorithms,
    imports,
    tests,
};

/// Identify section from YAML key
pub fn identifySection(key: []const u8) Section {
    if (std.mem.eql(u8, key, "name") or
        std.mem.eql(u8, key, "version") or
        std.mem.eql(u8, key, "language") or
        std.mem.eql(u8, key, "module") or
        std.mem.eql(u8, key, "description") or
        std.mem.eql(u8, key, "author") or
        std.mem.eql(u8, key, "license"))
        return .header;

    if (std.mem.eql(u8, key, "types")) return .types;
    if (std.mem.eql(u8, key, "behaviors") or std.mem.eql(u8, key, "functions")) return .behaviors;
    if (std.mem.eql(u8, key, "constants")) return .constants;
    if (std.mem.eql(u8, key, "algorithms")) return .algorithms;
    if (std.mem.eql(u8, key, "imports")) return .imports;
    if (std.mem.eql(u8, key, "test_cases") or std.mem.eql(u8, key, "tests")) return .tests;

    return .none;
}

// ============================================================================
// MAIN PARSER
// ============================================================================

/// Where a captured block scalar is delivered when the block ends.
const BlockTarget = enum {
    /// Consume the block without storing it. Not optional: block bodies
    /// contain colons ("Key difference: uses ...") and would otherwise be
    /// re-parsed as keys and invent phantom types and behaviours.
    discard,
    spec_description,
    type_description,
    behavior_given,
    behavior_when,
    behavior_then,
    behavior_implementation,
    constant_description,
};

/// Which nested list an `algorithms:` entry is currently filling.
const AlgoList = enum { none, inputs, outputs, steps };

/// Line-oriented state machine over the indentation-based YAML subset the
/// corpus actually uses. All nesting decisions are *relative* (compare against
/// the indent of the enclosing key), so a spec indented 4-wide parses the same
/// as one indented 2-wide.
const Builder = struct {
    gpa: Allocator,
    sa: Allocator,
    result: *ParseResult,

    section: Section = .none,

    block_target: ?BlockTarget = null,
    block_indent: usize = 0,
    block_cols: usize = 0,
    block_buf: ArrayList(u8) = .empty,

    ty: ?TypeDef = null,
    ty_indent: usize = 0,
    ty_fields_indent: ?usize = null,
    ty_enum_indent: ?usize = null,
    ty_constraints_indent: ?usize = null,
    field: ?Field = null,
    field_indent: usize = 0,

    bh: ?Behavior = null,
    bh_indent: usize = 0,
    bh_tc_indent: ?usize = null,

    tc: ?TestCase = null,
    tc_indent: usize = 0,
    tc_into_behavior: bool = false,

    ct: ?parser_types.Constant = null,
    ct_indent: usize = 0,

    im: ?parser_types.Import = null,
    im_indent: usize = 0,

    ag: ?parser_types.Algorithm = null,
    ag_indent: usize = 0,
    ag_list: AlgoList = .none,
    ag_list_indent: usize = 0,

    const Self = @This();

    fn dup(self: *Self, s: []const u8) ![]const u8 {
        return self.sa.dupe(u8, s);
    }

    /// Flow-sequence form of a list: `enum: [a, b, c]` on one line, as
    /// opposed to the block form handled in typesLine. Same cleaning rules as
    /// that path -- trim, unquote, skip empties -- so the two spellings of the
    /// same list produce identical entries.
    fn inlineList(self: *Self, value: []const u8, out: *ArrayList([]const u8)) !void {
        var inner = std.mem.trim(u8, value, " \t\r");
        if (inner.len >= 1 and inner[0] == '[') inner = inner[1..];
        if (inner.len >= 1 and inner[inner.len - 1] == ']') inner = inner[0 .. inner.len - 1];

        var it = std.mem.splitScalar(u8, inner, ',');
        while (it.next()) |raw| {
            const v = unquote(std.mem.trim(u8, raw, " \t\r"));
            if (v.len == 0) continue;
            try out.append(self.gpa, try self.dup(v));
        }
    }

    /// Assign a header field that `VibeeSpec.deinit` will free with `gpa`.
    /// Values equal to the struct's default literal are stored as the literal,
    /// mirroring deinit's own skip conditions exactly.
    fn setHeader(self: *Self, slot: *[]const u8, default_lit: []const u8, value: []const u8) !void {
        if (slot.len > 0 and !std.mem.eql(u8, slot.*, default_lit)) {
            self.gpa.free(slot.*);
        }
        if (value.len == 0 or std.mem.eql(u8, value, default_lit)) {
            slot.* = default_lit;
        } else {
            slot.* = try self.gpa.dupe(u8, value);
        }
    }

    fn warn(self: *Self, comptime fmt: []const u8, args: anytype) !void {
        const msg = try std.fmt.allocPrint(self.gpa, fmt, args);
        errdefer self.gpa.free(msg);
        try self.result.warnings.append(self.gpa, msg);
    }

    // ---- block scalars ----------------------------------------------------

    fn startBlock(self: *Self, target: BlockTarget, indent: usize, cols: usize) void {
        self.block_target = target;
        self.block_indent = indent;
        self.block_cols = cols;
        self.block_buf.clearRetainingCapacity();
    }

    fn appendBlockLine(self: *Self, raw: []const u8) !void {
        const trimmed_right = std.mem.trimEnd(u8, raw, " \t\r");
        const strip = self.block_cols + 2;
        const body = if (trimmed_right.len >= strip and
            std.mem.allEqual(u8, trimmed_right[0..strip], ' '))
            trimmed_right[strip..]
        else
            std.mem.trimStart(u8, trimmed_right, " \t");
        if (self.block_buf.items.len > 0) try self.block_buf.append(self.sa, '\n');
        try self.block_buf.appendSlice(self.sa, body);
    }

    fn endBlock(self: *Self) !void {
        const target = self.block_target orelse return;
        self.block_target = null;
        const text = std.mem.trim(u8, self.block_buf.items, " \t\r\n");
        switch (target) {
            .discard => {},
            .spec_description => try self.setHeader(&self.result.spec.description, "", text),
            .type_description => if (self.ty) |*t| {
                t.description = try self.dup(text);
            },
            .behavior_given => if (self.bh) |*b| {
                b.given = try self.dup(text);
            },
            .behavior_when => if (self.bh) |*b| {
                b.when = try self.dup(text);
            },
            .behavior_then => if (self.bh) |*b| {
                b.then = try self.dup(text);
            },
            .behavior_implementation => if (self.bh) |*b| {
                b.implementation = try self.dup(text);
            },
            .constant_description => if (self.ct) |*c| {
                c.description = try self.dup(text);
            },
        }
        self.block_buf.clearRetainingCapacity();
    }

    // ---- flushes ----------------------------------------------------------

    fn flushField(self: *Self) !void {
        const f = self.field orelse return;
        self.field = null;
        if (f.name.len == 0) return;
        if (f.type_name.len == 0) {
            // Emitting a typeless field would produce `name: ,` -- invalid Zig.
            try self.warn(
                "field '{s}' in type '{s}' has no type; skipped",
                .{ f.name, if (self.ty) |t| t.name else "?" },
            );
            return;
        }
        if (self.ty) |*t| try t.fields.append(self.gpa, f);
    }

    fn flushType(self: *Self) !void {
        try self.flushField();
        self.ty_fields_indent = null;
        self.ty_enum_indent = null;
        self.ty_constraints_indent = null;
        var t = self.ty orelse return;
        self.ty = null;
        if (t.name.len == 0) {
            t.deinit(self.gpa);
            return;
        }
        try self.result.spec.types.append(self.gpa, t);
    }

    fn flushTestCase(self: *Self) !void {
        const t = self.tc orelse return;
        self.tc = null;
        if (t.name.len == 0 and t.input.len == 0 and t.expected.len == 0) return;
        if (self.tc_into_behavior) {
            if (self.bh) |*b| try b.test_cases.append(self.gpa, t);
        } else {
            try self.result.spec.tests.append(self.gpa, t);
        }
    }

    fn flushBehavior(self: *Self) !void {
        try self.flushTestCase();
        self.bh_tc_indent = null;
        var b = self.bh orelse return;
        self.bh = null;
        if (b.name.len == 0) {
            b.deinit(self.gpa);
            return;
        }
        try self.result.spec.behaviors.append(self.gpa, b);
    }

    fn flushConstant(self: *Self) !void {
        const c = self.ct orelse return;
        self.ct = null;
        if (c.name.len == 0) return;
        try self.result.spec.constants.append(self.gpa, c);
    }

    fn flushImport(self: *Self) !void {
        const i = self.im orelse return;
        self.im = null;
        if (i.name.len == 0) return;
        try self.result.spec.imports.append(self.gpa, i);
    }

    fn flushAlgorithm(self: *Self) !void {
        self.ag_list = .none;
        var a = self.ag orelse return;
        self.ag = null;
        if (a.name.len == 0) {
            a.deinit(self.gpa);
            return;
        }
        try self.result.spec.algorithms.append(self.gpa, a);
    }

    fn flushAll(self: *Self) !void {
        try self.endBlock();
        try self.flushType();
        try self.flushBehavior();
        try self.flushConstant();
        try self.flushImport();
        try self.flushAlgorithm();
        try self.flushTestCase();
    }

    // ---- sections ---------------------------------------------------------

    fn topLevel(self: *Self, line: []const u8) !void {
        try self.flushAll();
        const key, const value, const ok = parseKeyValue(line);
        if (!ok) return;

        self.section = identifySection(key);

        if (self.section == .header) {
            if (std.mem.eql(u8, key, "description") and isBlockScalar(value)) {
                self.startBlock(.spec_description, 0, 0);
                return;
            }
            if (std.mem.eql(u8, key, "name")) {
                try self.setHeader(&self.result.spec.name, "", value);
            } else if (std.mem.eql(u8, key, "version")) {
                try self.setHeader(&self.result.spec.version, "1.0.0", value);
            } else if (std.mem.eql(u8, key, "language")) {
                try self.setHeader(&self.result.spec.language, "zig", value);
            } else if (std.mem.eql(u8, key, "module")) {
                try self.setHeader(&self.result.spec.module, "", value);
            } else if (std.mem.eql(u8, key, "description")) {
                try self.setHeader(&self.result.spec.description, "", value);
            } else if (std.mem.eql(u8, key, "author")) {
                try self.setHeader(&self.result.spec.author, "", value);
            } else if (std.mem.eql(u8, key, "license")) {
                try self.setHeader(&self.result.spec.license, "MIT", value);
            }
            return;
        }

        // An unrecognised top-level key (`problem:`, `export_functions:`, ...)
        // sets section to .none so its indented body is skipped rather than
        // being attributed to whatever section came before it.
        if (isBlockScalar(value)) self.startBlock(.discard, 0, 0);
    }

    fn typesLine(self: *Self, body: []const u8, indent: usize, cols: usize) !void {
        if (self.ty_enum_indent) |ei| {
            if (indent > ei) {
                const item = listItemBody(body) orelse body;
                const v = unquote(std.mem.trim(u8, item, " \t\r"));
                if (v.len > 0 and self.ty != null) {
                    try self.ty.?.enum_variants.append(self.gpa, try self.dup(v));
                }
                return;
            }
            self.ty_enum_indent = null;
        }
        if (self.ty_constraints_indent) |ci| {
            if (indent > ci) {
                const item = listItemBody(body) orelse body;
                const v = unquote(std.mem.trim(u8, item, " \t\r"));
                if (v.len > 0 and self.ty != null) {
                    try self.ty.?.constraints.append(self.gpa, try self.dup(v));
                }
                return;
            }
            self.ty_constraints_indent = null;
        }
        if (self.ty_fields_indent) |fi| {
            if (indent > fi) return self.fieldLine(body, indent, cols);
            try self.flushField();
            self.ty_fields_indent = null;
        }

        if (self.ty != null and indent > self.ty_indent) {
            const key, const value, const ok = parseKeyValue(body);
            if (!ok) return;
            if (std.mem.eql(u8, key, "fields")) {
                self.ty_fields_indent = indent;
            } else if (std.mem.eql(u8, key, "enum") or std.mem.eql(u8, key, "variants")) {
                if (value.len > 0 and value[0] == '[') {
                    try self.inlineList(value, &self.ty.?.enum_variants);
                } else {
                    self.ty_enum_indent = indent;
                }
            } else if (std.mem.eql(u8, key, "constraints")) {
                self.ty_constraints_indent = indent;
            } else if (std.mem.eql(u8, key, "description")) {
                if (isBlockScalar(value)) {
                    self.startBlock(.type_description, indent, cols);
                } else {
                    self.ty.?.description = try self.dup(value);
                }
            } else if (std.mem.eql(u8, key, "base") or std.mem.eql(u8, key, "extends")) {
                if (value.len > 0) self.ty.?.base = try self.dup(value);
            } else if (std.mem.eql(u8, key, "generic")) {
                if (value.len > 0) self.ty.?.generic = try self.dup(value);
            } else if (isBlockScalar(value)) {
                self.startBlock(.discard, indent, cols);
            }
            return;
        }

        // New type declaration: `Name:` or `- Name:`.
        try self.flushType();
        const item = listItemBody(body) orelse body;
        const key, const value, const ok = parseKeyValue(item);
        if (!ok or key.len == 0) return;
        var t = TypeDef.init(self.gpa);
        t.name = try self.dup(key);
        self.ty = t;
        self.ty_indent = indent;
        if (isBlockScalar(value)) self.startBlock(.discard, indent, cols);
    }

    fn fieldLine(self: *Self, body: []const u8, indent: usize, cols: usize) !void {
        if (listItemBody(body)) |item| {
            try self.flushField();
            const key, const value, const ok = parseKeyValue(item);
            if (!ok or key.len == 0) return;
            if (std.mem.eql(u8, key, "name") and value.len > 0) {
                // `- name: x` / `type: y` form -- wait for the sibling `type:`.
                self.field = .{ .name = try self.dup(value), .type_name = "" };
            } else {
                // `- field_name: Type` form.
                self.field = .{ .name = try self.dup(key), .type_name = try self.dup(unquote(value)) };
            }
            self.field_indent = indent;
            return;
        }

        const key, const value, const ok = parseKeyValue(body);
        if (!ok or key.len == 0) return;

        if (self.field != null and indent > self.field_indent) {
            if (std.mem.eql(u8, key, "type") and self.field.?.type_name.len == 0) {
                self.field.?.type_name = try self.dup(unquote(value));
            } else if (std.mem.eql(u8, key, "constraint")) {
                self.field.?.constraint = try self.dup(value);
            } else if (isBlockScalar(value)) {
                self.startBlock(.discard, indent, cols);
            }
            return;
        }

        // Mapping form: `field_name: Type`.
        try self.flushField();
        if (isBlockScalar(value)) {
            self.startBlock(.discard, indent, cols);
            return;
        }
        self.field = .{ .name = try self.dup(key), .type_name = try self.dup(unquote(value)) };
        self.field_indent = indent;
    }

    fn behaviorsLine(self: *Self, body: []const u8, indent: usize, cols: usize) !void {
        if (self.bh_tc_indent) |ti| {
            if (indent > ti) return self.testCaseLine(body, indent, cols);
            try self.flushTestCase();
            self.bh_tc_indent = null;
        }

        if (self.bh != null and indent > self.bh_indent) {
            // Nested list items belong to `params:` / `steps:` / `returns:`
            // sub-structures the target types have no room for.
            if (listItemBody(body) != null) return;
            const key, const value, const ok = parseKeyValue(body);
            if (!ok) return;
            if (std.mem.eql(u8, key, "given")) {
                if (isBlockScalar(value)) {
                    self.startBlock(.behavior_given, indent, cols);
                } else self.bh.?.given = try self.dup(value);
            } else if (std.mem.eql(u8, key, "when")) {
                if (isBlockScalar(value)) {
                    self.startBlock(.behavior_when, indent, cols);
                } else self.bh.?.when = try self.dup(value);
            } else if (std.mem.eql(u8, key, "then")) {
                if (isBlockScalar(value)) {
                    self.startBlock(.behavior_then, indent, cols);
                } else self.bh.?.then = try self.dup(value);
            } else if (std.mem.eql(u8, key, "implementation") or std.mem.eql(u8, key, "impl")) {
                if (isBlockScalar(value)) {
                    self.startBlock(.behavior_implementation, indent, cols);
                } else self.bh.?.implementation = try self.dup(value);
            } else if (std.mem.eql(u8, key, "owner")) {
                if (value.len > 0) self.bh.?.owner = try self.dup(value);
            } else if (std.mem.eql(u8, key, "name")) {
                if (value.len > 0) self.bh.?.name = try self.dup(value);
            } else if (std.mem.eql(u8, key, "test_cases") or std.mem.eql(u8, key, "tests")) {
                self.bh_tc_indent = indent;
                self.tc_into_behavior = true;
            } else if (isBlockScalar(value)) {
                self.startBlock(.discard, indent, cols);
            }
            return;
        }

        try self.flushBehavior();
        var b = Behavior.init(self.gpa);
        const is_list = listItemBody(body) != null;
        const item = listItemBody(body) orelse body;
        const key, const value, const ok = parseKeyValue(item);
        if (!ok) {
            // Bare bullet: `- doSomething`
            if (is_list and item.len > 0) {
                b.name = try self.dup(unquote(item));
            } else {
                b.deinit(self.gpa);
                return;
            }
        } else if (is_list and std.mem.eql(u8, key, "name") and value.len > 0) {
            b.name = try self.dup(value);
        } else {
            if (key.len == 0) {
                b.deinit(self.gpa);
                return;
            }
            b.name = try self.dup(key);
            if (isBlockScalar(value)) self.startBlock(.discard, indent, cols);
        }
        self.bh = b;
        self.bh_indent = indent;
    }

    fn testCaseLine(self: *Self, body: []const u8, indent: usize, cols: usize) !void {
        if (listItemBody(body)) |item| {
            try self.flushTestCase();
            var t = TestCase{ .name = "", .input = "", .expected = "", .tolerance = null };
            const key, const value, const ok = parseKeyValue(item);
            if (ok) {
                if (std.mem.eql(u8, key, "name")) {
                    t.name = try self.dup(value);
                } else {
                    t.name = try self.dup(key);
                }
            } else if (item.len > 0) {
                t.name = try self.dup(unquote(item));
            }
            self.tc = t;
            self.tc_indent = indent;
            return;
        }
        if (self.tc == null or indent <= self.tc_indent) return;
        const key, const value, const ok = parseKeyValue(body);
        if (!ok) return;
        if (std.mem.eql(u8, key, "name")) {
            self.tc.?.name = try self.dup(value);
        } else if (std.mem.eql(u8, key, "input") or
            (std.mem.eql(u8, key, "given") and self.tc.?.input.len == 0))
        {
            self.tc.?.input = try self.dup(value);
        } else if (std.mem.eql(u8, key, "expected") or
            (std.mem.eql(u8, key, "then") and self.tc.?.expected.len == 0))
        {
            self.tc.?.expected = try self.dup(value);
        } else if (std.mem.eql(u8, key, "tolerance")) {
            self.tc.?.tolerance = std.fmt.parseFloat(f64, value) catch null;
        } else if (isBlockScalar(value)) {
            self.startBlock(.discard, indent, cols);
        }
    }

    fn constantsLine(self: *Self, body: []const u8, indent: usize, cols: usize) !void {
        if (self.ct != null and indent > self.ct_indent) {
            const key, const value, const ok = parseKeyValue(body);
            if (!ok) return;
            if (std.mem.eql(u8, key, "value")) {
                self.setConstantValue(&self.ct.?, value) catch |e| return e;
            } else if (std.mem.eql(u8, key, "description")) {
                if (isBlockScalar(value)) {
                    self.startBlock(.constant_description, indent, cols);
                } else self.ct.?.description = try self.dup(value);
            } else if (isBlockScalar(value)) {
                self.startBlock(.discard, indent, cols);
            }
            return;
        }

        try self.flushConstant();
        const is_list = listItemBody(body) != null;
        const item = listItemBody(body) orelse body;
        const key, const value, const ok = parseKeyValue(item);
        if (!ok or key.len == 0) return;
        var c = parser_types.Constant{
            .name = "",
            .value = 0,
            .string_value = "",
            .is_string = false,
            .description = "",
        };
        if (is_list and std.mem.eql(u8, key, "name") and value.len > 0) {
            c.name = try self.dup(value);
        } else {
            c.name = try self.dup(key);
            if (isBlockScalar(value)) {
                self.startBlock(.discard, indent, cols);
            } else if (value.len > 0) {
                try self.setConstantValue(&c, value);
            }
        }
        self.ct = c;
        self.ct_indent = indent;
    }

    fn setConstantValue(self: *Self, c: *parser_types.Constant, raw: []const u8) !void {
        const v = unquote(raw);
        if (v.len == 0) return;
        if (std.fmt.parseFloat(f64, v)) |n| {
            c.value = n;
            c.is_string = false;
            c.string_value = "";
        } else |_| {
            c.is_string = true;
            c.string_value = try self.dup(v);
        }
    }

    fn importsLine(self: *Self, body: []const u8, indent: usize) !void {
        if (self.im != null and indent > self.im_indent) {
            const key, const value, const ok = parseKeyValue(body);
            if (!ok) return;
            if (std.mem.eql(u8, key, "path") or std.mem.eql(u8, key, "from")) {
                self.im.?.path = try self.dup(unquote(value));
            }
            return;
        }
        try self.flushImport();
        const is_list = listItemBody(body) != null;
        const item = listItemBody(body) orelse body;
        const key, const value, const ok = parseKeyValue(item);
        var im = parser_types.Import{ .name = "", .path = "" };
        if (!ok) {
            if (!is_list or item.len == 0) return;
            im.name = try self.dup(unquote(item)); // `- pas_mining_core`
        } else if (std.mem.eql(u8, key, "name") or std.mem.eql(u8, key, "module")) {
            if (value.len == 0) return;
            im.name = try self.dup(value);
        } else {
            im.name = try self.dup(key);
            im.path = try self.dup(unquote(value));
        }
        self.im = im;
        self.im_indent = indent;
    }

    fn algorithmsLine(self: *Self, body: []const u8, indent: usize) !void {
        if (self.ag_list != .none) {
            if (indent > self.ag_list_indent) {
                const item = listItemBody(body) orelse body;
                const key, const value, const ok = parseKeyValue(item);
                const text = if (ok and std.mem.eql(u8, key, "name")) value else unquote(item);
                if (text.len > 0 and self.ag != null) {
                    const dst = switch (self.ag_list) {
                        .inputs => &self.ag.?.inputs,
                        .outputs => &self.ag.?.outputs,
                        .steps => &self.ag.?.steps,
                        .none => unreachable,
                    };
                    try dst.append(self.gpa, try self.dup(text));
                }
                return;
            }
            self.ag_list = .none;
        }

        if (self.ag != null and indent > self.ag_indent) {
            const key, const value, const ok = parseKeyValue(body);
            if (!ok) return;
            const list: AlgoList = if (std.mem.eql(u8, key, "inputs") or std.mem.eql(u8, key, "input"))
                .inputs
            else if (std.mem.eql(u8, key, "outputs") or std.mem.eql(u8, key, "output"))
                .outputs
            else if (std.mem.eql(u8, key, "steps"))
                .steps
            else
                .none;
            if (list != .none) {
                if (value.len > 0 and !isBlockScalar(value)) {
                    const dst = switch (list) {
                        .inputs => &self.ag.?.inputs,
                        .outputs => &self.ag.?.outputs,
                        .steps => &self.ag.?.steps,
                        .none => unreachable,
                    };
                    try dst.append(self.gpa, try self.dup(unquote(value)));
                } else {
                    self.ag_list = list;
                    self.ag_list_indent = indent;
                }
            } else if (std.mem.eql(u8, key, "big_o") or std.mem.eql(u8, key, "complexity")) {
                self.ag.?.big_o = try self.dup(value);
            }
            return;
        }

        try self.flushAlgorithm();
        const is_list = listItemBody(body) != null;
        const item = listItemBody(body) orelse body;
        const key, const value, const ok = parseKeyValue(item);
        if (!ok or key.len == 0) return;
        var a = parser_types.Algorithm.init(self.gpa);
        a.name = if (is_list and std.mem.eql(u8, key, "name") and value.len > 0)
            try self.dup(value)
        else
            try self.dup(key);
        self.ag = a;
        self.ag_indent = indent;
    }
};

/// Parse .tri specification file from source string
pub fn parse(allocator: Allocator, source: []const u8) !ParseResult {
    var result = ParseResult.init(allocator);
    errdefer result.deinit(allocator);

    var b = Builder{
        .gpa = allocator,
        .sa = result.strings.allocator(),
        .result = &result,
    };

    var lines = std.mem.splitScalar(u8, source, '\n');
    while (lines.next()) |raw| {
        // Block scalars swallow everything more indented than their key,
        // comments and blank lines included, so this runs before the skips.
        if (b.block_target != null) {
            if (isEmptyLine(raw)) {
                try b.appendBlockLine("");
                continue;
            }
            if (getIndentLevel(raw) > b.block_indent) {
                try b.appendBlockLine(raw);
                continue;
            }
            try b.endBlock();
        }

        if (isComment(raw) or isEmptyLine(raw)) continue;

        const line = stripInlineComment(raw);
        if (line.len == 0) continue;

        const indent = getIndentLevel(line);
        if (indent == 0) {
            try b.topLevel(line);
            continue;
        }

        var cols: usize = 0;
        while (cols < line.len and line[cols] == ' ') cols += 1;
        const body = std.mem.trim(u8, line, " \t\r");

        switch (b.section) {
            .types => try b.typesLine(body, indent, cols),
            .behaviors => try b.behaviorsLine(body, indent, cols),
            .constants => try b.constantsLine(body, indent, cols),
            .imports => try b.importsLine(body, indent),
            .algorithms => try b.algorithmsLine(body, indent),
            .tests => {
                b.tc_into_behavior = false;
                try b.testCaseLine(body, indent, cols);
            },
            .none, .header, .functions => {},
        }
    }

    try b.flushAll();

    return result;
}

/// Parse .tri specification from file
pub fn parseFile(allocator: Allocator, file_path: []const u8) !ParseResult {
    const io = tri_io.get();
    const source = try std.Io.Dir.cwd().readFileAlloc(io, file_path, allocator, .limited(1024 * 1024));
    defer allocator.free(source);

    return parse(allocator, source);
}

// ============================================================================
// VALIDATION
// ============================================================================

/// Validate parsed specification
pub fn validate(allocator: Allocator, spec: *const VibeeSpec) !ArrayList([]const u8) {
    var errors = try ArrayList([]const u8).initCapacity(allocator, 10);

    // Check required fields
    if (spec.name.len == 0) {
        try errors.append(allocator, try allocator.dupe(u8, "Missing required field: name"));
    }
    if (spec.module.len == 0) {
        try errors.append(allocator, try allocator.dupe(u8, "Missing required field: module"));
    }

    // Check language is supported
    if (!std.mem.eql(u8, spec.language, "zig") and
        !std.mem.eql(u8, spec.language, "varlog") and
        !std.mem.eql(u8, spec.language, "python"))
    {
        try errors.append(allocator, try allocator.dupe(u8, "Unsupported language (must be: zig, varlog, or python)"));
    }

    return errors;
}

// ============================================================================
// TESTS
// ============================================================================

test "VIBEE Parser: parseKeyValue basic" {
    const line = "name: my_module";
    const key, const value, const ok = parseKeyValue(line);

    try std.testing.expect(ok);
    try std.testing.expectEqualStrings("name", key);
    try std.testing.expectEqualStrings("my_module", value);
}

test "VIBEE Parser: parseKeyValue with quotes" {
    const line = "description: \"A test module\"";
    const key, const value, const ok = parseKeyValue(line);

    try std.testing.expect(ok);
    try std.testing.expectEqualStrings("description", key);
    try std.testing.expectEqualStrings("A test module", value);
}

test "VIBEE Parser: isComment" {
    try std.testing.expect(isComment("# This is a comment"));
    try std.testing.expect(isComment("  # Indented comment"));
    try std.testing.expect(!isComment("not_a_comment = value"));
}

test "VIBEE Parser: isEmptyLine" {
    try std.testing.expect(isEmptyLine(""));
    try std.testing.expect(isEmptyLine("   "));
    try std.testing.expect(isEmptyLine("\t\n"));
    try std.testing.expect(!isEmptyLine("key = value"));
}

test "VIBEE Parser: getIndentLevel" {
    try std.testing.expectEqual(@as(usize, 0), getIndentLevel("key: value"));
    try std.testing.expectEqual(@as(usize, 1), getIndentLevel("  key: value"));
    try std.testing.expectEqual(@as(usize, 2), getIndentLevel("    key: value"));
}

test "VIBEE Parser: isListItem" {
    try std.testing.expect(isListItem("- item1"));
    try std.testing.expect(isListItem("  - item2"));
    try std.testing.expect(!isListItem("key: value"));
}

test "VIBEE Parser: extractListItem" {
    try std.testing.expectEqualStrings("item1", extractListItem("- item1"));
    try std.testing.expectEqualStrings("my_value", extractListItem("- my_value"));
    try std.testing.expectEqualStrings("unquoted", extractListItem("- \"unquoted\""));
}

test "VIBEE Parser: parse minimal spec" {
    const allocator = std.testing.allocator;
    const source =
        \\name: test_module
        \\version: "1.0.0"
        \\language: zig
        \\module: test.module
        \\description: "Test module"
    ;

    var result = try parse(allocator, source);
    defer result.deinit(allocator);

    try std.testing.expect(result.success());
    try std.testing.expectEqualStrings("test_module", result.spec.name);
    try std.testing.expectEqualStrings("zig", result.spec.language);
}

test "VIBEE Parser: validate missing name" {
    const allocator = std.testing.allocator;
    var spec = VibeeSpec.init(allocator);
    defer spec.deinit(allocator);

    // Duped, not a literal: deinit frees any non-default string field, so a
    // literal here frees read-only memory. See the ownership contract on
    // VibeeSpec.deinit -- this line used to abort the whole test binary.
    spec.module = try allocator.dupe(u8, "test.module");
    spec.language = "zig"; // the init default, which deinit correctly skips

    var errors = try validate(allocator, &spec);
    defer {
        for (errors.items) |err| allocator.free(err);
        errors.deinit(allocator);
    }

    try std.testing.expect(errors.items.len > 0);
}

// ─── The parse body ────────────────────────────────────────────────────────
//
// These pin the loop that was missing entirely: `parse` handled indent == 0
// and had no branch at all for indented lines, so `current_type_name` and
// `current_behavior_name` were assigned and never read, and nothing was ever
// appended to spec.types or spec.behaviors. Every spec in the repo parsed to
// a header and stopped, and the generator emitted files with no types and no
// behaviour functions.
//
// A test that only checks the header would still have passed against that
// stub. Each of these fails against it.

test "a types section produces types, with their fields" {
    const allocator = std.testing.allocator;
    const source =
        \\name: shapes
        \\version: "2.0.0"
        \\language: zig
        \\
        \\types:
        \\  Point:
        \\    fields:
        \\      x: Float
        \\      y: Float
        \\
        \\  Label:
        \\    fields:
        \\      text: String
        \\      size: Uint32
    ;
    var result = try parse(allocator, source);
    defer result.deinit(allocator);

    try std.testing.expectEqual(@as(usize, 2), result.spec.types.items.len);

    const point = result.spec.types.items[0];
    try std.testing.expectEqualStrings("Point", point.name);
    try std.testing.expectEqual(@as(usize, 2), point.fields.items.len);
    try std.testing.expectEqualStrings("x", point.fields.items[0].name);
    try std.testing.expectEqualStrings("Float", point.fields.items[0].type_name);

    const label = result.spec.types.items[1];
    try std.testing.expectEqualStrings("Label", label.name);
    try std.testing.expectEqual(@as(usize, 2), label.fields.items.len);
    // The spec's own spelling reaches the field; lowering to u32 is
    // codegen/utils.zig's job, not the parser's.
    try std.testing.expectEqualStrings("Uint32", label.fields.items[1].type_name);
}

test "a behaviors section produces behaviours, with given/when/then" {
    const allocator = std.testing.allocator;
    const source =
        \\name: oracle
        \\language: zig
        \\
        \\behaviors:
        \\  getPrice:
        \\    given: "chain_id"
        \\    when: "a price is requested"
        \\    then: "Returns the current price"
        \\
        \\  setPrice:
        \\    given: "chain_id, price"
        \\    when: "an update arrives"
        \\    then: "Stores it"
    ;
    var result = try parse(allocator, source);
    defer result.deinit(allocator);

    try std.testing.expectEqual(@as(usize, 2), result.spec.behaviors.items.len);

    const get = result.spec.behaviors.items[0];
    try std.testing.expectEqualStrings("getPrice", get.name);
    // Quotes are stripped: a `given` of `"chain_id"` must not arrive with its
    // quotation marks still attached, or every generated doc comment carries them.
    try std.testing.expectEqualStrings("chain_id", get.given);
    try std.testing.expectEqualStrings("a price is requested", get.when);
    try std.testing.expectEqualStrings("Returns the current price", get.then);

    try std.testing.expectEqualStrings("setPrice", result.spec.behaviors.items[1].name);
}

test "a trailing comment is not part of the value" {
    const allocator = std.testing.allocator;
    const source =
        \\name: commented
        \\language: zig
        \\
        \\types:
        \\  Thing:
        \\    fields:
        \\      id: String # the unique identifier
    ;
    var result = try parse(allocator, source);
    defer result.deinit(allocator);

    try std.testing.expectEqual(@as(usize, 1), result.spec.types.items.len);
    const f = result.spec.types.items[0].fields.items[0];
    try std.testing.expectEqualStrings("id", f.name);
    try std.testing.expectEqualStrings("String", f.type_name);
}

test "an empty section yields an empty list, not a phantom entry" {
    const allocator = std.testing.allocator;
    const source =
        \\name: hollow
        \\language: zig
        \\
        \\types:
        \\
        \\behaviors:
    ;
    var result = try parse(allocator, source);
    defer result.deinit(allocator);

    try std.testing.expectEqual(@as(usize, 0), result.spec.types.items.len);
    try std.testing.expectEqual(@as(usize, 0), result.spec.behaviors.items.len);
    // The header must still land -- an empty body is not a parse failure.
    try std.testing.expectEqualStrings("hollow", result.spec.name);
}

test "the header still parses when sections follow it" {
    // The stub got this right and everything else wrong, so this is the
    // control: it must keep passing, and on its own it proves nothing.
    const allocator = std.testing.allocator;
    const source =
        \\name: header_check
        \\version: "3.1.4"
        \\language: zig
        \\module: tri
        \\
        \\types:
        \\  A:
        \\    fields:
        \\      v: Int
    ;
    var result = try parse(allocator, source);
    defer result.deinit(allocator);

    try std.testing.expectEqualStrings("header_check", result.spec.name);
    try std.testing.expectEqualStrings("3.1.4", result.spec.version);
    try std.testing.expectEqualStrings("tri", result.spec.module);
    try std.testing.expectEqual(@as(usize, 1), result.spec.types.items.len);
}
