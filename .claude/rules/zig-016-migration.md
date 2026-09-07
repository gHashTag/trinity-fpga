# Zig 0.16 Migration

The toolchain in this environment is Zig **0.16.0**. Much of `src/` was written
against 0.15. This file records what 0.16 actually removed, what replaces each
thing, and — more usefully — the traps that a mechanical rename walks straight
into.

Every entry below was confirmed against the installed stdlib at
`/opt/homebrew/Cellar/zig/0.16.0_1/lib/zig/std`. Several plausible guesses
turned out to be wrong (`makeOpenPath`, `File.writeAll`, "`Child.run` was just
deleted"), so **check the stdlib source before trusting any rename you have not
personally verified.**

## The shim modules

Six modules restore removed stdlib surface. They exist so that call sites change
by one word instead of by a signature:

| Module | Replaces |
|---|---|
| `tri_time` | `std.time.timestamp` / `milli` / `micro` / `nanoTimestamp`, `std.time.Timer`, `std.Thread.sleep` |
| `tri_env` | `std.process.getEnvVarOwned`, `hasEnvVarConstant`, `getEnvMap`, `std.posix.getenv` |
| `tri_proc` | `std.process.Child.run` |
| `tri_io` | the process-wide `Io` handle |
| `tri_mutex` | `std.Thread.Mutex` (this is `src/tri/mutex.zig`, which predates the rest) |
| `tri_rand` | `std.crypto.random` |

**All six are build modules, imported by name** — `@import("tri_time")`, never
a relative path. A single file may not belong to two modules; path-importing
one of these from a second module fails with
`file exists in modules 'root' and '...'`. If a new module needs one, add it to
that module's `.imports` in `build.zig`.

## When to shim and when to thread

This is the only judgement call in the migration, and getting it backwards is
expensive in both directions.

- **Ambient facts** — wall-clock time, environment variables, running a
  subprocess — get a **shim**. There is no reason to make them substitutable
  here, and threading an `Io` to 2924 timestamp sites would change the
  signature of every function in between.
- **Real capabilities** — file I/O — get **actual `Io` threading**. That is the
  point of the 0.16 change, and shimming it away would discard the benefit.

## `tri_io.get()` is a last resort

Use it **only** when the call chain crosses a build-module boundary and an `io`
parameter would mean changing signatures in modules that have no other reason
to know about `Io`.

**If the function already has an `io` parameter, or the struct has an `io`
field, use that.** Reaching for the ambient handle when one is in scope defeats
the migration. `main` installs the process `Io` via `tri_io.install(io)`; the
lazy fallback in `get()` is for tests, not for production paths.

## Rename table

    std.fs.Dir / std.fs.File          -> std.Io.Dir / std.Io.File
    std.fs.cwd()                      -> std.Io.Dir.cwd()
    dir.openFile(p, .{})              -> dir.openFile(io, p, .{})
    dir.createFile(p, .{})            -> dir.createFile(io, p, .{})
    dir.openDir(p, .{})               -> dir.openDir(io, p, .{})
    dir.access / deleteFile / statFile-> same, with io as the first argument
    dir.makePath(p)                   -> dir.createDirPath(io, p)
    dir.readFileAlloc(gpa, p, n)      -> dir.readFileAlloc(io, p, gpa, .limited(n))
    iter.next()                       -> iter.next(io)      [dir.iterate() itself is unchanged]
    file.close() / file.stat()        -> file.close(io) / file.stat(io)
    file.writeAll(b)                  -> file.writeStreamingAll(io, b)
    file.seekFromEnd(0) + writeAll(b) -> const end = try file.length(io);
                                         try file.writePositionalAll(io, b, end);
    std.fs.createFileAbsolute(p, f)   -> std.Io.Dir.createFileAbsolute(io, p, f)
    std.fs.File.stdin()               -> std.Io.File.stdin()
    std.mem.trimLeft / trimRight      -> std.mem.trimStart / trimEnd
    std.meta.intToEnum(E, v)          -> std.enums.fromInt(E, v)   [see trap 4]
    std.io.fixedBufferStream(&buf)    -> var w: std.Io.Writer = .fixed(&buf);
                                         ... w.buffered() for what was written
    list.writer(gpa)                  -> var aw: std.Io.Writer.Allocating = .init(gpa);
                                         const w = &aw.writer;  ... aw.toOwnedSlice()
    std.http.Client{ .allocator = a } -> also needs .io
    Child.Term .Exited                -> .exited  (and .signal / .stopped / .unknown)

Note `dir.readFileAlloc` **changed argument order**, and the whole-file read
lives on the **directory**, not the file — `open` + `readToEndAlloc` + `close`
collapses into one call.

`std.time` still has its unit constants (`ns_per_ms`, `ms_per_s`, …) and
`epoch`. Do not rewrite those.

## The traps

### 1. `readAll` has no direct replacement, and the obvious one is wrong

0.15 `file.readAll(buf)` filled the buffer, stopped early **only** at EOF, and
returned the count.

`readStreaming` is **not** that. It is a single attempt that may return fewer
bytes than requested — **including 0** — without being at end-of-file, and it
signals end-of-stream with `error.EndOfStream` rather than a `0` return. That
is the exact inverse of the 0.15 contract, so translating the call while
keeping the old condition silently turns every short read into an EOF, or
decodes a partly-filled buffer as data.

Choose by what a short read *means* at that site:

- **Whole small file into a fixed buffer, short reads normal** →
  `std.Io.Dir.cwd().readFile(io, path, &buf)`, which returns the slice read.
  Usually the right answer, and it replaces open+readAll+close in one call.
- **Sequential fixed-width binary fields, where short means corrupt** →
  `file.reader(io, &scratch)` then `readSliceAll`, which loops until full and
  errors `EndOfStream` if it cannot fill.
- **Read what is there, short is legitimate** → `readSliceShort`, which returns
  a short count if and only if the stream ended.

Picking `readSliceAll` where short reads are normal turns every ordinary read
into an error; picking `readSliceShort` where they mean corruption hides the
corruption. Both mistakes were made and caught during this migration.

### 2. A shim is validated by its call sites, not by its own tests

`tri_time.Timer.start` was first written infallible. Its own tests passed 5/5.
It broke all ~130 call sites, because the `std.time.Timer` it replaces returned
an **error union** and every site here `try`s or `catch`es it.

When restoring a removed API, the existing call sites are the specification.
`tri_time` now has a test that asserts exactly that, and it is the most useful
test in the file.

### 3. Scope a rename by what the pattern *matches*, not by what it looks like

`.Unknown`, `.Signal` and `.Stopped` look like `Child.Term` tags. In this tree
`.Unknown` is overwhelmingly `error.UnknownOpcode` and project-defined enum
variants (91 occurrences), and `.Signal`/`.Stopped` collide with
`parser_types.Signal` and an unrelated status enum. Only `.Exited` — which
nothing else in the tree declares — was safe to rewrite globally.

Likewise, `.writer()` appears 429 times but only **73** are ArrayList-backed;
the rest are file and stdout writers this axis does not touch.

**Count what a pattern matches, then sample it, before running it tree-wide.**

### 4. `intToEnum` returned an error union; `fromInt` returns an optional

So `catch X` becomes `orelse X`, and an `else |_|` branch becomes a plain
`else`. A regex cannot bound where the `catch` default expression ends — doing
this by regex produced unbalanced parens in three files.

### 5. `ArrayList` is unmanaged and `.{}` no longer constructs one

Use `.empty`. The compiler reports this as `missing struct field: items`, which
does not sound like an ArrayList problem at all. Also `append(gpa, x)` and
`deinit(gpa)`.

### 6. `std.Io.Writer.fixed` fails with a different error

`error.WriteFailed`, where `FixedBufferStream` gave `error.NoSpaceLeft`. It
still fills the buffer before failing, so truncation behaviour is preserved —
but a `catch` that matches on the old name will not fire.

## Working practice

- **The error list is a frontier, not a total.** Zig analyses lazily, so
  clearing one file exposes the next. Count **files cleared**, not errors.
- `zig build-obj` on a library file proves almost nothing — with no root
  reference, nothing is semantically analysed and it returns `rc=0` on code
  that cannot compile. Use `zig test <file>`, or compile through the real root.
- `zig ast-check` proves a file **parses**. It does not prove it compiles.
- Roughly 32 files in this tree do not parse **on `main`** (garbled identifiers,
  stray bytes). Do not mistake them for migration damage, and do not try to
  repair them as part of a migration.
- Before any tree-wide rewrite: back the file up, and gate the restore on a
  parse check **in the same shell command**, so a broken result cannot outlive
  the invocation that produced it.

## Before writing a shim: check whether the tree already has one

Search for the **name of the removed API**, not just its call sites. An
existing replacement will usually mention it — in a comment, or in a
`@hasDecl` version guard — even when no call site uses it any more:

```bash
grep -rn "std.Thread.Mutex" src/ | grep -v "std.Thread.Mutex;"
```

This was learned the expensive way. `src/tri/mutex.zig` already replaced
`std.Thread.Mutex` behind a version guard and already had 12 users; a second
implementation was written, tested, wired into six modules and swept across 44
files before anyone noticed. One grep, up front, would have found it.

## Never apply a bare text replacement to an identifier

Scope it to code. The text most likely to contain the string you are replacing
is **a comment explaining the very migration you are doing**, and the second
most likely is **a string literal in a code generator**. Both were corrupted in
this migration:

- `mutex.zig`'s own `@hasDecl(std.Thread, "Mutex")` guard became
  self-referential nonsense.
- Four generators would have emitted `@import("tri_io")` into standalone files
  that have no such module.

Neither is visible to `zig ast-check`: one is a comment, the other is inside a
string.

## Automate behind a gate, never in front of one

Every tree-wide pass in this migration now follows the same shape:

1. Count what the pattern matches, then **sample** what it matches.
2. Refuse the file outright if it contains a shape the transform does not model
   (e.g. a writer passed as a bare argument to `std.fmt.format`).
3. Transform, re-run `zig ast-check`, and **restore the original on failure**.

That gate skipped 14 files and auto-reverted 3 across two passes, with nothing
damaged. The passes that ran *without* it are the ones that had to be reverted
wholesale afterwards.

## Deriving module dependencies instead of guessing them

When a shim becomes a build module, every module whose file set imports it
needs the dependency. Compute this rather than chasing `no module named` errors
one build at a time: for each `createModule` in `build.zig`, walk its own
`@import` graph and collect which shims appear, then add exactly what is
missing. That resolved 55 modules in a single pass.

Two failure modes to expect, neither of which `zig fmt` catches — they are
build-graph errors, not parse errors:

- **Declaration order.** A module referenced before it is declared fails with
  `use of undeclared identifier`. Put the shim modules at the very top.
- **`.imports` in the wrong struct.** `addExecutable` has no `imports` field; it
  belongs to the `createModule` nested inside it.

And note that an error grep anchored to `^src/` will silently miss a
`build.zig:` error entirely, which looks exactly like success.

## Scope every sweep to the tree you mean

A sweep that walked `.` instead of `src/` rewrote 19 files in
`deploy/trinity-nexus/` and `fpga/tools/` — **separate Zig workspaces** whose
`build.zig` declares none of these modules. Every one of them would have
broken. This repo contains more than one build graph; a migration belongs to
exactly one of them.

