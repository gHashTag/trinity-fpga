// ═══════════════════════════════════════════════════════════════════════════════
// VIBEE GEN - Minimal Code Generator
// ═══════════════════════════════════════════════════════════════════════════════
//
// Generates Zig/Verilog code from .vibee specifications
// Single source of truth: .vibee specs -> generated code
//
// φ² + 1/φ² = 3 = TRINITY
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");
const tri_io = @import("tri_io");
const vibee_parser = @import("vibee_parser.zig");
const zig_codegen = @import("zig_codegen.zig");
const verilog_codegen = @import("verilog_codegen.zig");
const lang_generators = @import("lang_generators.zig");

/// Does this source use t27's block syntax rather than VIBEE's YAML?
///
/// Deliberately requires the ABSENCE of a top-level `name:` as well as the
/// presence of a t27 marker. 42 of our own specs contain `spec ` at the start
/// of a line while still being YAML, so the marker alone would reject them.
fn looksLikeT27(source: []const u8) bool {
    if (hasVibeeName(source)) return false;

    const markers = [_][]const u8{ "\nspec ", "\ninvariant ", "\nnumericformat ", "\npub fn " };
    for (markers) |m| {
        if (std.mem.indexOf(u8, source, m) != null) return true;
    }
    return std.mem.startsWith(u8, source, "spec ");
}

fn hasVibeeName(source: []const u8) bool {
    return std.mem.startsWith(u8, source, "name:") or
        std.mem.indexOf(u8, source, "\nname:") != null;
}

/// Which foreign language is this, if any?
///
/// `specs/` holds FOUR languages under the `.tri` extension, not two. A census
/// of all 1137 specs:
///
///     YAML VIBEE      `name:` at line start        1065
///     t27 blocks      `spec X { }`                   14
///     Markdown        `## headings`                  32
///     TOML            `[section]`, `key = "value"`   13
///     comment-led     starts with `//`               10
///     near-empty      under 3 non-blank lines         3
///
/// On every one of the 72 non-YAML specs this generator used to report
/// `Types: 0, Behaviors: 0` and write boilerplate, silently, exit 0 -- and the
/// corpus gate cannot object, because it counts 0/0 as a legitimate spec with
/// no behaviours.
///
/// Returns the language's name for the error message, or null when the source
/// is VIBEE or unrecognised. Unrecognised falls through on purpose: a wrong
/// refusal breaks a working pipeline, while a miss only preserves today's
/// behaviour.
fn foreignDialect(source: []const u8) ?[]const u8 {
    if (hasVibeeName(source)) return null;

    // Markdown FIRST, because a prose document can embed code in any language.
    // `specs/storm_main.tri` is Markdown containing a Zig block with
    // `pub fn executeStormCommand(...)`, and checking t27's markers first
    // labelled it a t27 spec. The refusal was right and the name was wrong,
    // which is worse than useless in an error message.
    //
    // An ATX heading is required, not a bare `#`: `#` is also VIBEE's comment
    // character, and a spec opening `# Adagrad` is a comment, not a heading.
    if (std.mem.startsWith(u8, source, "## ") or std.mem.indexOf(u8, source, "\n## ") != null) {
        return "Markdown";
    }

    // TOML: a `[section]` header plus a `key = value` line.
    if (std.mem.startsWith(u8, source, "[") or std.mem.indexOf(u8, source, "\n[") != null) {
        if (std.mem.indexOf(u8, source, " = ") != null) return "TOML";
    }

    if (looksLikeT27(source)) return "t27";
    return null;
}

pub fn main(init: std.process.Init.Minimal) !void {
    const allocator = std.heap.page_allocator;

    const args = try init.args.toSlice(allocator);
    defer allocator.free(args);
    if (args.len < 2) {
        printUsage();
        return;
    }

    const command = args[1];

    if (std.mem.eql(u8, command, "gen")) {
        if (args.len < 3) {
            std.debug.print("Error: Missing input file\n", .{});
            printUsage();
            return;
        }

        const input_path = args[2];
        const language = detectLanguage(allocator, input_path) catch "zig";

        var derived_path: ?[]const u8 = null;
        defer if (derived_path) |p| allocator.free(p);

        const output_path = if (args.len > 3) args[3] else blk: {
            derived_path = deriveOutputPath(allocator, input_path, language) catch {
                std.debug.print("Error: Could not derive output path\n", .{});
                return;
            };
            break :blk derived_path.?;
        };

        try generateCode(allocator, input_path, output_path);
    } else if (std.mem.eql(u8, command, "koschei")) {
        printKoscheiCycle();
    } else if (std.mem.eql(u8, command, "help") or std.mem.eql(u8, command, "--help") or std.mem.eql(u8, command, "-h")) {
        printUsage();
    } else {
        std.debug.print("Unknown command: {s}\n", .{command});
        printUsage();
    }
}

fn printUsage() void {
    std.debug.print(
        \\
        \\╔══════════════════════════════════════════════════════════════╗
        \\║           VIBEE GEN - Code Generator                         ║
        \\║           Single Source of Truth: .vibee -> Code             ║
        \\╚══════════════════════════════════════════════════════════════╝
        \\
        \\Usage:
        \\  vibee_gen gen <spec.vibee> [output]   Generate code from spec
        \\  vibee_gen koschei                      Show 16-step cycle
        \\  vibee_gen help                         Show this help
        \\
        \\Examples:
        \\  vibee_gen gen specs/tri/trinity_cli.vibee
        \\  vibee_gen gen specs/tri/agent.vibee trinity/output/agent.zig
        \\
        \\Supported languages in .vibee:
        \\  language: zig         -> Generates .zig file
        \\  language: varlog      -> Generates .v (Verilog) file
        \\  language: python      -> Generates .py file
        \\  language: typescript  -> Generates .ts file
        \\  language: rust        -> Generates .rs file
        \\  language: go          -> Generates .go file
        \\  language: java        -> Generates .java file
        \\  language: swift       -> Generates .swift file
        \\  language: kotlin      -> Generates .kt file
        \\  language: c           -> Generates .h file
        \\  language: sql         -> Generates .sql file
        \\
        \\φ² + 1/φ² = 3 = TRINITY
        \\
    , .{});
}

fn printKoscheiCycle() void {
    std.debug.print(
        \\
        \\╔══════════════════════════════════════════════════════════════╗
        \\║           KOSCHEI 16-STEP DEVELOPMENT CYCLE                  ║
        \\║           Mandatory Process for All Changes                  ║
        \\╚══════════════════════════════════════════════════════════════╝
        \\
        \\SPECIFICATION (Steps 1-4):
        \\  1. Create .vibee specification (SINGLE SOURCE OF TRUTH)
        \\  2. Define types (data structures)
        \\  3. Define behaviors (functions)
        \\  4. Add algorithms if needed
        \\
        \\GENERATION (Steps 5-8):
        \\  5. Run: vibee_gen gen <spec.vibee>
        \\  6. Review generated code
        \\  7. Run tests: zig build test
        \\  8. Fix any issues in SPEC (not generated code!)
        \\
        \\VALIDATION (Steps 9-12):
        \\  9. Run benchmarks
        \\  10. Write critical assessment (honest self-criticism)
        \\  11. Document achievements
        \\  12. Update technology tree
        \\
        \\DEPLOYMENT (Steps 13-16):
        \\  13. Git add & commit
        \\  14. Push to remote
        \\  15. Propose 3 tech tree options for next iteration
        \\  16. Loop back to step 1
        \\
        \\RULES:
        \\  - NEVER edit generated code directly
        \\  - ALL changes go through .vibee specs
        \\  - One source of truth = no duplication
        \\
        \\φ² + 1/φ² = 3 = TRINITY
        \\
    , .{});
}

/// Write generated code, or leave nothing behind.
///
/// The shipped `tools/bin/vibee_gen` created the output file, failed the
/// write, printed `error.Unexpected`, and **returned leaving a 0-byte file on
/// disk**. That is how `tools/bin/vibee_arm64` came to be 0 bytes and stay
/// that way: an empty file is indistinguishable from a successful run to
/// every downstream check. `zig ast-check` returns rc=0 on an empty file, and
/// so does `zig fmt --check`.
///
/// So the contract here is all-or-nothing. On any write failure the partial
/// file is deleted before the error is reported, and the error is reported
/// rather than swallowed.
fn writeGenerated(output_path: []const u8, generated_code: []const u8) !void {
    const io = tri_io.get();

    var output_file = std.Io.Dir.cwd().createFile(io, output_path, .{}) catch |err| {
        std.debug.print("Error creating output file: {}\n", .{err});
        return err;
    };

    output_file.writeStreamingAll(io, generated_code) catch |err| {
        std.debug.print("Error writing output: {}\n", .{err});
        output_file.close(io);
        // Do not leave a truncated artefact where a generated file should be.
        std.Io.Dir.cwd().deleteFile(io, output_path) catch |del_err| {
            std.debug.print(
                "  and could not remove the partial file {s}: {}\n",
                .{ output_path, del_err },
            );
        };
        return err;
    };
    output_file.close(io);

    if (generated_code.len == 0) {
        // A generator that emits nothing has not succeeded, whatever the
        // write returned. Refuse rather than report success over an empty file.
        std.Io.Dir.cwd().deleteFile(io, output_path) catch {};
        std.debug.print("Error: the generator produced 0 bytes for {s}\n", .{output_path});
        return error.EmptyOutput;
    }
}

fn detectLanguage(allocator: std.mem.Allocator, input_path: []const u8) ![]const u8 {
    // Read the head of the file to detect the language field.
    //
    // This was `file.read(&buf)` on a 4 KiB stack buffer. In 0.16 a single
    // read is ONE attempt that may return short without meaning EOF, so a
    // `language:` field sitting past the first short read would have gone
    // undetected. readFileAlloc reads the whole file or fails; the limit
    // bounds it, and specs in this repo are a few KiB.
    const content = try std.Io.Dir.cwd().readFileAlloc(
        tri_io.get(),
        input_path,
        allocator,
        .limited(1024 * 1024),
    );
    defer allocator.free(content);

    // Look for "language:" field
    if (std.mem.indexOf(u8, content, "language:")) |idx| {
        var end_idx = idx + 9;
        // Skip whitespace
        while (end_idx < content.len and (content[end_idx] == ' ' or content[end_idx] == '\t' or content[end_idx] == '"')) {
            end_idx += 1;
        }
        // Check for array syntax [zig, python, ...]
        if (end_idx < content.len and content[end_idx] == '[') {
            end_idx += 1; // skip '['
            // Skip whitespace after '['
            while (end_idx < content.len and (content[end_idx] == ' ' or content[end_idx] == '\t')) {
                end_idx += 1;
            }
            const start = end_idx;
            // Read first language in array (up to comma, space, or ']')
            while (end_idx < content.len and content[end_idx] != ',' and content[end_idx] != ']' and content[end_idx] != ' ') {
                end_idx += 1;
            }
            if (end_idx > start) {
                return try allocator.dupe(u8, content[start..end_idx]);
            }
        }
        const start = end_idx;
        // Find end of value
        while (end_idx < content.len and content[end_idx] != '\n' and content[end_idx] != '"' and content[end_idx] != ' ') {
            end_idx += 1;
        }
        if (end_idx > start) {
            return try allocator.dupe(u8, content[start..end_idx]);
        }
    }

    return "zig"; // Default
}

fn deriveOutputPath(allocator: std.mem.Allocator, input_path: []const u8, language: []const u8) ![]const u8 {
    // Get base name without extension
    const base = std.fs.path.basename(input_path);
    const name_end = std.mem.lastIndexOf(u8, base, ".") orelse base.len;
    const name = base[0..name_end];

    // Determine extension based on language
    const ext = if (std.mem.eql(u8, language, "varlog") or std.mem.eql(u8, language, "verilog"))
        ".v"
    else if (std.mem.eql(u8, language, "python"))
        ".py"
    else if (std.mem.eql(u8, language, "typescript"))
        ".ts"
    else if (std.mem.eql(u8, language, "rust"))
        ".rs"
    else if (std.mem.eql(u8, language, "go"))
        ".go"
    else if (std.mem.eql(u8, language, "java"))
        ".java"
    else if (std.mem.eql(u8, language, "swift"))
        ".swift"
    else if (std.mem.eql(u8, language, "kotlin"))
        ".kt"
    else if (std.mem.eql(u8, language, "c"))
        ".h"
    else if (std.mem.eql(u8, language, "sql"))
        ".sql"
    else
        ".zig";

    // Build output path: trinity/output/<name><ext>
    return try std.fmt.allocPrint(allocator, "trinity/output/{s}{s}", .{ name, ext });
}

fn generateCode(allocator: std.mem.Allocator, input_path: []const u8, output_path: []const u8) !void {
    std.debug.print("\n╔══════════════════════════════════════════════════════════════╗\n", .{});
    std.debug.print("║  VIBEE CODE GENERATION                                       ║\n", .{});
    std.debug.print("╚══════════════════════════════════════════════════════════════╝\n\n", .{});

    std.debug.print("Input:  {s}\n", .{input_path});
    std.debug.print("Output: {s}\n\n", .{output_path});

    // Read source file.
    //
    // Was open + stat + alloc(stat.size) + readAll, then BOTH
    // `defer allocator.free(source)` and `spec.owns_source = true` -- which
    // makes the spec free it too. That is a double free of the whole source
    // buffer on every successful run. readFileAlloc gives one allocation with
    // one owner, and the ownership is handed to the spec below.
    const source = std.Io.Dir.cwd().readFileAlloc(
        tri_io.get(),
        input_path,
        allocator,
        .limited(16 * 1024 * 1024),
    ) catch |err| {
        std.debug.print("Error reading file: {}\n", .{err});
        return;
    };
    // Registered BEFORE the parse defer, so it runs AFTER it: the spec may
    // hold slices into `source`, and freeing the backing buffer first would
    // make every later read of spec.name a use-after-free.
    defer allocator.free(source);

    // Parse specification.
    //
    // `vibee_parser.VibeeParser` no longer exists -- the parser was rewritten
    // as free functions and re-exported from gen_vibee_parser.zig, and nothing
    // updated this caller. That rewrite is why the shipped tools/bin/vibee_gen
    // could not be rebuilt from this source: the binary predates it.
    std.debug.print("Parsing specification...\n", .{});
    var result = vibee_parser.parse(allocator, source) catch |err| {
        std.debug.print("Error parsing spec: {}\n", .{err});
        return;
    };
    defer result.deinit(allocator);

    for (result.errors.items) |e| std.debug.print("  spec error: {s}\n", .{e});
    for (result.warnings.items) |w| std.debug.print("  spec warning: {s}\n", .{w});

    const spec = &result.spec;

    std.debug.print("  Name: {s}\n", .{spec.name});
    std.debug.print("  Version: {s}\n", .{spec.version});
    std.debug.print("  Language: {s}\n", .{spec.language});
    std.debug.print("  Types: {d}\n", .{spec.types.items.len});
    std.debug.print("  Behaviors: {d}\n", .{spec.behaviors.items.len});

    // Refuse a spec written in the OTHER .tri language.
    //
    // trinity-fpga and the t27 project both use the `.tri` extension for
    // completely different languages. VIBEE specs are YAML with a top-level
    // `name:`; t27 specs are block-structured -- `spec X { ... }`,
    // `pub fn f(x f32) -> gf16`, `invariant { assert ... }`.
    //
    // Pointed at a t27 spec, this generator reported `Types: 0, Behaviors: 0`
    // and wrote 3945 bytes of boilerplate, silently, exit 0. During a
    // migration from one language to the other that is the worst possible
    // behaviour: the wrong tool quietly produces a plausible-looking file.
    //
    // The discriminator is `name:`, measured over both corpora: 1066 of our
    // 1137 specs have it, 0 of t27's do. The 71 without it are checked for
    // t27 block syntax before rejecting, so a VIBEE spec that merely omits a
    // header still generates.
    if (spec.types.items.len == 0 and spec.behaviors.items.len == 0) {
        if (foreignDialect(source)) |dialect| {
            std.debug.print(
                \\
                \\  ERROR: {s} looks like a {s} spec, not a VIBEE spec.
                \\  Four languages share the .tri extension in this tree; this
                \\  generator reads only the YAML form with a top-level `name:`.
                \\  A t27 spec compiles with `t27c gen`; Markdown and TOML have
                \\  no generator at all and are probably misfiled.
                \\
            , .{ input_path, dialect });
            return error.NotAVibeeSpec;
        }
    }

    // The multi-language branch that stood here read `spec.languages`, a field
    // the current VibeeSpec does not have -- the parser rewrite replaced the
    // list with a single `language`. The branch was therefore unreachable for
    // as long as both existed, and could not compile. `generateSingleLang` is
    // kept below and still works; restoring multi-target output needs the
    // parser to carry a list again, which is a spec-format decision, not a
    // repair.

    // Ensure output directory exists
    const dir_path = std.fs.path.dirname(output_path) orelse ".";
    std.Io.Dir.cwd().createDirPath(tri_io.get(), dir_path) catch {};

    // Generate code based on language
    var generated_code: []const u8 = undefined;

    if (std.mem.eql(u8, spec.language, "varlog") or std.mem.eql(u8, spec.language, "verilog")) {
        std.debug.print("\nGenerating Verilog...\n", .{});
        var codegen = verilog_codegen.VerilogCodeGen.init(allocator);
        defer codegen.deinit();
        generated_code = try codegen.generate(spec);
    } else if (isMultiLangTarget(spec.language)) {
        std.debug.print("\nGenerating {s}...\n", .{spec.language});
        generated_code = try generateMultiLang(allocator, spec);
    } else {
        std.debug.print("\nGenerating Zig...\n", .{});
        var codegen = zig_codegen.ZigCodeGen.init(allocator);
        defer codegen.deinit();
        generated_code = try codegen.generate(spec);
    }

    // Write to output file
    defer allocator.free(generated_code);
    writeGenerated(output_path, generated_code) catch return;

    std.debug.print("\n✓ Code generated successfully!\n", .{});
    std.debug.print("  Output: {s}\n", .{output_path});
    std.debug.print("\nφ² + 1/φ² = 3 = TRINITY\n\n", .{});
}

fn generateSingleLang(allocator: std.mem.Allocator, spec: *vibee_parser.VibeeSpec, language: []const u8, lang_output: []const u8) !void {
    const dir_path = std.fs.path.dirname(lang_output) orelse ".";
    std.Io.Dir.cwd().createDirPath(tri_io.get(), dir_path) catch {};

    var generated_code: []const u8 = undefined;

    if (std.mem.eql(u8, language, "varlog") or std.mem.eql(u8, language, "verilog")) {
        std.debug.print("\nGenerating Verilog...\n", .{});
        var codegen = verilog_codegen.VerilogCodeGen.init(allocator);
        defer codegen.deinit();
        generated_code = try codegen.generate(spec);
    } else if (isMultiLangTarget(language)) {
        std.debug.print("\nGenerating {s}...\n", .{language});
        // Temporarily set spec.language for the generator
        const orig_lang = spec.language;
        spec.language = language;
        generated_code = try generateMultiLang(allocator, spec);
        spec.language = orig_lang;
    } else {
        std.debug.print("\nGenerating Zig...\n", .{});
        var codegen = zig_codegen.ZigCodeGen.init(allocator);
        defer codegen.deinit();
        generated_code = try codegen.generate(spec);
    }

    defer allocator.free(generated_code);
    writeGenerated(lang_output, generated_code) catch return;

    std.debug.print("  -> {s}\n", .{lang_output});
}

fn isMultiLangTarget(language: []const u8) bool {
    const targets = [_][]const u8{
        "python", "typescript", "rust",   "go",
        "java",   "swift",      "kotlin", "c",
        "sql",
    };
    for (targets) |t| {
        if (std.mem.eql(u8, language, t)) return true;
    }
    return false;
}

fn generateMultiLang(allocator: std.mem.Allocator, spec: *vibee_parser.VibeeSpec) ![]const u8 {
    // Convert VibeeSpec types to lang_generators.ParsedSpec format
    var types_buf = try allocator.alloc(lang_generators.TypeDef, spec.types.items.len);
    defer allocator.free(types_buf);

    var fields_bufs = try allocator.alloc([]const lang_generators.Field, spec.types.items.len);
    defer {
        for (fields_bufs) |fb| allocator.free(fb);
        allocator.free(fields_bufs);
    }

    for (spec.types.items, 0..) |t, i| {
        var fields = try allocator.alloc(lang_generators.Field, t.fields.items.len);
        for (t.fields.items, 0..) |f, j| {
            fields[j] = .{ .name = f.name, .type_name = f.type_name };
        }
        fields_bufs[i] = fields;
        types_buf[i] = .{ .name = t.name, .fields = fields };
    }

    var behaviors_buf = try allocator.alloc(lang_generators.Behavior, spec.behaviors.items.len);
    defer allocator.free(behaviors_buf);

    for (spec.behaviors.items, 0..) |b, i| {
        behaviors_buf[i] = .{
            .name = b.name,
            .given = b.given,
            .when = b.when,
            .then = b.then,
            .implementation = b.implementation,
        };
    }

    const parsed = lang_generators.ParsedSpec{
        .name = spec.name,
        .version = spec.version,
        .types = types_buf,
        .behaviors = behaviors_buf,
    };

    return lang_generators.generateForLanguage(allocator, parsed, spec.language);
}
