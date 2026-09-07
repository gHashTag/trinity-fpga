// ═══════════════════════════════════════════════════════════════════════════════
// ZIG CODE GENERATION - Facade for modular codegen
// ═══════════════════════════════════════════════════════════════════════════════
//
// This file is a facade that re-exports the modular codegen components.
// The actual implementation is split into:
//   - codegen/types.zig      - Type definitions
//   - codegen/builder.zig    - CodeBuilder for output generation
//   - codegen/utils.zig      - Utility functions (mapType, etc.)
//   - codegen/patterns.zig   - Pattern matching (DSL, VSA, Metal, etc.)
//   - codegen/tests_gen.zig  - Test generation from behaviors
//   - codegen/emitter.zig    - Main ZigCodeGen engine
//   - codegen/mod.zig        - Module re-exports
//
// φ² + 1/φ² = 3
//
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");
const tri_io = @import("tri_io");
const Allocator = std.mem.Allocator;

// Import modular components
pub const codegen = @import("codegen/mod.zig");
pub const vibee_parser = @import("vibee_parser.zig");

// Re-export main types
pub const ZigCodeGen = codegen.ZigCodeGen;
pub const CodeBuilder = codegen.CodeBuilder;
pub const PatternMatcher = codegen.PatternMatcher;
pub const TestGenerator = codegen.TestGenerator;

// Re-export parser types
pub const VibeeSpec = vibee_parser.VibeeSpec;
pub const Behavior = vibee_parser.Behavior;
pub const TypeDef = vibee_parser.TypeDef;
pub const Constant = vibee_parser.Constant;
pub const CreationPattern = vibee_parser.CreationPattern;
pub const TestCase = vibee_parser.TestCase;

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN ENTRY POINT - For backward compatibility
// ═══════════════════════════════════════════════════════════════════════════════

/// Generate Zig code from a .tri file
pub fn generateFromFile(allocator: Allocator, vibee_path: []const u8, output_path: []const u8) !void {
    const io = tri_io.get();

    // Read .tri file
    const source = try std.Io.Dir.cwd().readFileAlloc(io, vibee_path, allocator, .limited(1024 * 1024));
    defer allocator.free(source);

    // Parse
    var parser = vibee_parser.VibeeParser.init(allocator, source);
    var spec = try parser.parse();
    defer spec.deinit();

    // Generate Zig code
    var gen = ZigCodeGen.init(allocator);
    defer gen.deinit();

    const output = try gen.generate(&spec);

    // Write to file
    const out_file = try std.Io.Dir.cwd().createFile(io, output_path, .{});
    defer out_file.close(io);

    try out_file.writeStreamingAll(io, output);
}

/// Generate Zig code from a VibeeSpec (for programmatic use)
pub fn generateFromSpec(allocator: Allocator, spec: *const VibeeSpec) ![]const u8 {
    var gen = ZigCodeGen.init(allocator);
    defer gen.deinit();
    return try gen.generate(spec);
}

// ═══════════════════════════════════════════════════════════════════════════════
// TESTS
// ═══════════════════════════════════════════════════════════════════════════════

test "zig_codegen facade imports" {
    _ = ZigCodeGen;
    _ = CodeBuilder;
    _ = PatternMatcher;
    _ = TestGenerator;
    std.debug.print("Facade imports successful\n", .{});
}

test "codegen submodules" {
    _ = @import("codegen/types.zig");
    _ = @import("codegen/builder.zig");
    _ = @import("codegen/utils.zig");
    _ = @import("codegen/patterns.zig");
    _ = @import("codegen/tests_gen.zig");
    _ = @import("codegen/emitter.zig");
    _ = @import("codegen/mod.zig");
}

// ─── Signature and body must agree ─────────────────────────────────────────
//
// Two independent decisions, keyed on two different things:
//
//   the RETURN TYPE comes from phrases in the behaviour's `then` clause
//       (signature.zig: "valid" -> bool, "count" -> usize, ...)
//   the BODY SHAPE comes from the prefix of the behaviour's NAME
//       (emitter.zig: process*/run*/execute* -> a timed block, ...)
//
// Nothing makes them agree, and they demonstrably do not: a `then` reading
// "Return true if phi^2 + 1/phi^2 equals 3.0" produced `!void` while
// tests_gen emitted `try std.testing.expect(result)`, and the generated file
// did not compile. That was one instance found by CI; this is the general
// property.
//
// The invariant a generated function must satisfy is small and checkable on
// the emitted text: if the signature promises a value, the body must return
// one. This sweeps the whole name-prefix space against the whole return-type
// space, so a new body branch that forgets to return is caught the first time
// it is added, rather than whenever a spec happens to hit it.

const parser_types_align = @import("gen_parser_types.zig");

/// Extract the body of `pub fn <name>(` from generated source: everything
/// between its opening brace and the first `\n}` at column zero.
fn bodyOf(src: []const u8, fn_name: []const u8) ?struct { ret: []const u8, body: []const u8 } {
    var needle_buf: [128]u8 = undefined;
    const needle = std.fmt.bufPrint(&needle_buf, "pub fn {s}(", .{fn_name}) catch return null;
    const at = std.mem.indexOf(u8, src, needle) orelse return null;

    const line_end = std.mem.indexOfScalarPos(u8, src, at, '\n') orelse return null;
    const header = src[at..line_end];
    const close_paren = std.mem.lastIndexOfScalar(u8, header, ')') orelse return null;
    const brace = std.mem.lastIndexOfScalar(u8, header, '{') orelse return null;
    if (brace < close_paren) return null;
    const ret = std.mem.trim(u8, header[close_paren + 1 .. brace], " ");

    const body_start = line_end + 1;
    const end_rel = std.mem.indexOf(u8, src[body_start..], "\n}") orelse return null;
    return .{ .ret = ret, .body = src[body_start .. body_start + end_rel] };
}

/// Does this return type oblige the body to produce a value?
fn returnsAValue(ret: []const u8) bool {
    if (ret.len == 0) return false;
    if (std.mem.eql(u8, ret, "void") or std.mem.eql(u8, ret, "!void")) return false;
    if (std.mem.eql(u8, ret, "anyerror!void")) return false;
    return true;
}

test "a generated function that promises a value returns one" {
    const allocator = std.testing.allocator;

    // Every prefix emitter.zig and body_emitter.zig branch on. Kept as a
    // literal list rather than derived, so adding a branch without adding it
    // here leaves a visible gap rather than silently shrinking the sweep.
    const prefixes = [_][]const u8{
        "add",      "assemble",   "assign",    "boost",    "check",
        "classify", "clear",      "combine",   "compress", "compute",
        "convert",  "coordinate", "decay",     "decode",   "decompress",
        "delegate", "delete",     "detect",    "disable",  "dispatch",
        "encode",   "estimate",   "evict",     "execute",  "extract",
        "find",     "fit",        "fuse",      "generate", "get",
        "handle",   "insert",     "list",      "load",     "merge",
        "modify",   "parse",      "persist",   "process",  "query",
        "recall",   "reinforce",  "remove",    "reset",    "resolve",
        "respond",  "route",      "run",       "save",     "score",
        "search",   "select",     "set",       "should",   "start",
        "stream",   "strengthen", "summarize", "trim",     "update",
        "validate", "verify",
    };

    // One phrase per return type signature.zig can select, plus the phrasing
    // that started this: "Return true" (capital R, no s) misses the
    // "returns true" entry and falls through to !void.
    const thens = [_][]const u8{
        "Returns a similarity score",
        "Returns the count of items",
        "Returns encoded bytes",
        "Returns the weights",
        "Returns true or false",
        "Return true if the identity holds",
        "Returns an array of results",
        "Returns the text label",
        "Stores the value",
    };

    var checked: usize = 0;
    var bad: usize = 0;

    for (prefixes) |p| {
        for (thens) |t| {
            var name_buf: [64]u8 = undefined;
            const name = try std.fmt.bufPrint(&name_buf, "{s}Thing", .{p});

            var spec = parser_types_align.VibeeSpec.init(allocator);
            defer spec.deinit(allocator);

            var b = parser_types_align.Behavior.init(allocator);
            b.name = name;
            b.given = "input";
            b.when = "asked";
            b.then = t;
            try spec.behaviors.append(allocator, b);

            var gen = ZigCodeGen.init(allocator);
            defer gen.deinit();
            const out = try gen.generate(&spec);
            defer allocator.free(out);

            const found = bodyOf(out, name) orelse continue;
            if (!returnsAValue(found.ret)) continue;

            checked += 1;
            if (std.mem.indexOf(u8, found.body, "return ") == null) {
                std.debug.print(
                    "  {s} + \"{s}\" -> signature `{s}` with a body that never returns\n",
                    .{ name, t, found.ret },
                );
                bad += 1;
            }
        }
    }

    // The property under test.
    try std.testing.expectEqual(@as(usize, 0), bad);

    // Guard the denominator. This assertion used to read
    // `expectEqual(0, checked)` -- because the emitter hardcoded `() !void`
    // and signature.zig's return-type inference reached the body emitter and
    // the test generator but never the function header. The sweep examined
    // nothing, and said so rather than passing quietly.
    //
    // The header now comes from the inference, so the sweep has real work:
    // 372 of the 558 combinations produce a value-returning signature, and
    // the `bad == 0` above is what checks each of them has a body to match.
    try std.testing.expect(checked > 100);
}

test "the function header comes from the spec's own then clause" {
    // The sharp form of the note above. This was a characterization test for
    // the opposite fact -- it asserted `!void`, because the header ignored
    // the inference entirely, which is what let tests_gen emit a bool
    // assertion against a function that returned nothing and broke CI.
    const allocator = std.testing.allocator;

    var spec = parser_types_align.VibeeSpec.init(allocator);
    defer spec.deinit(allocator);

    var b = parser_types_align.Behavior.init(allocator);
    b.name = "computeSimilarity";
    b.given = "two vectors";
    // signature.zig maps "similarity" to f32 -- unambiguously, it is the
    // first phrase in its list.
    b.then = "Returns a similarity score";
    try spec.behaviors.append(allocator, b);

    var gen = ZigCodeGen.init(allocator);
    defer gen.deinit();
    const out = try gen.generate(&spec);
    defer allocator.free(out);

    const found = bodyOf(out, "computeSimilarity") orelse return error.FunctionNotEmitted;
    try std.testing.expectEqualStrings("f32", found.ret);
    // And a body that produces one, since the stub computes nothing.
    try std.testing.expect(std.mem.indexOf(u8, found.body, "return ") != null);
}

test "a behaviour's implementation lands inside a function, never at file scope" {
    // specs/needle/core.tri emitted its first behaviour's `implementation:`
    // block as bare statements after the BEHAVIOR FUNCTIONS banner -- no doc
    // comments, no `pub fn`, just `const parser = try ...` at file scope. The
    // generated file did not parse. Every other behaviour in the same spec
    // got a proper header.
    const allocator = std.testing.allocator;

    var spec = parser_types_align.VibeeSpec.init(allocator);
    defer spec.deinit(allocator);

    var b = parser_types_align.Behavior.init(allocator);
    b.name = "find_matches_ast";
    b.given = "Source code + AST loaded";
    b.when = "Pattern is a query";
    b.then = "Returns list of MatchResult";
    // A function BODY, not a definition: no `fn`, no `pub const`.
    b.implementation =
        \\const parser = try zig_parser.createZigParser();
        \\const root = parser.root();
        \\return root;
    ;
    try spec.behaviors.append(allocator, b);

    var gen = ZigCodeGen.init(allocator);
    defer gen.deinit();
    const out = try gen.generate(&spec);
    defer allocator.free(out);

    const impl_at = std.mem.indexOf(u8, out, "const parser = try zig_parser") orelse
        return error.ImplementationNotEmitted;
    const header_at = std.mem.indexOf(u8, out, "pub fn find_matches_ast");

    if (header_at == null or header_at.? > impl_at) {
        std.debug.print(
            "  implementation emitted at file scope: no `pub fn find_matches_ast` before it\n",
            .{},
        );
    }
    try std.testing.expect(header_at != null);
    try std.testing.expect(header_at.? < impl_at);
}

// ─── Specs referencing types they never declare ────────────────────────────
//
// 365 field types across 146 specs name a type the spec neither declares in
// `types:` nor lists in `imports:`. The generator emits them faithfully, so
// the resulting Zig has an undeclared identifier -- 12 of the 19 undeclared
// identifiers in generated output were this.
//
// A ratchet, not a demand for zero: 365 is too many to fix in one change, and
// a permanently red gate reads as a broken subject rather than a broken check.
// This defends the number so the class cannot grow while it is worked down.

// 152, measured by THIS test. Running the generator binary over the corpus and
// counting its warnings gave 146 -- a different instrument, over a slightly
// different set (it counts only specs that generate successfully). The number
// a ratchet defends has to come from the instrument that enforces it, or the
// first honest run looks like a regression.
const baseline_undeclared_specs: usize = 152;

test "no NEW spec references a type it never declares" {
    const gpa = std.testing.allocator;

    const io = tri_io_for_test.get();

    var paths: std.ArrayList([]u8) = .empty;
    defer {
        for (paths.items) |p| gpa.free(p);
        paths.deinit(gpa);
    }
    collectSpecs(gpa, io, "specs", &paths) catch return error.SkipZigTest;

    var offending: usize = 0;
    var checked: usize = 0;
    for (paths.items) |path| {
        const src = std.Io.Dir.cwd().readFileAlloc(io, path, gpa, .limited(4 * 1024 * 1024)) catch continue;
        defer gpa.free(src);
        checked += 1;

        var result = spec_parser.parse(gpa, src) catch continue;
        defer result.deinit(gpa);

        if (specHasUndeclaredType(&result.spec)) offending += 1;
    }

    // Guard the denominator: a walk that finds no specs would pass over
    // nothing, which is the failure mode this repository keeps producing.
    try std.testing.expect(checked > 300);

    if (offending > baseline_undeclared_specs) {
        std.debug.print(
            "  {d} specs reference an undeclared type, up from the {d} baseline.\n" ++
                "  Add the type to `types:` or the module to `imports:`; if the\n" ++
                "  increase is intentional, update baseline_undeclared_specs.\n",
            .{ offending, baseline_undeclared_specs },
        );
    }
    try std.testing.expect(offending <= baseline_undeclared_specs);
}

/// Same rule the generator warns on: an uppercase field type that mapType does
/// not lower, and that the spec neither declares nor imports.
fn specHasUndeclaredType(spec: *const parser_types_align.VibeeSpec) bool {
    for (spec.types.items) |t| {
        for (t.fields.items) |f| {
            const bare = std.mem.trim(u8, f.type_name, " \t?[]*");
            if (bare.len == 0 or !std.ascii.isUpper(bare[0])) continue;
            if (!std.mem.eql(u8, codegen_utils_for_test.mapType(bare), bare)) continue;

            var declared = false;
            for (spec.types.items) |other| {
                if (std.mem.eql(u8, other.name, bare)) declared = true;
            }
            for (spec.imports.items) |imp| {
                if (std.mem.eql(u8, imp.name, bare)) declared = true;
            }
            if (!declared) return true;
        }
    }
    return false;
}

const codegen_utils_for_test = @import("codegen/utils.zig");
const spec_parser = @import("gen_vibee_parser.zig");
const tri_io_for_test = @import("tri_io");

fn collectSpecs(gpa: std.mem.Allocator, io: std.Io, path: []const u8, acc: *std.ArrayList([]u8)) !void {
    var dir = try std.Io.Dir.cwd().openDir(io, path, .{ .iterate = true });
    defer dir.close(io);

    var it = dir.iterate();
    while (try it.next(io)) |entry| {
        if (entry.name.len > 0 and entry.name[0] == '.') continue;
        const child = try std.fs.path.join(gpa, &.{ path, entry.name });
        switch (entry.kind) {
            .directory => {
                defer gpa.free(child);
                collectSpecs(gpa, io, child, acc) catch {};
            },
            .file => {
                if (std.mem.endsWith(u8, entry.name, ".vibee") or
                    std.mem.endsWith(u8, entry.name, ".tri"))
                {
                    try acc.append(gpa, child);
                } else gpa.free(child);
            },
            else => gpa.free(child),
        }
    }
}
