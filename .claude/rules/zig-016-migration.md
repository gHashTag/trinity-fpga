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

Four modules restore removed stdlib surface. They exist so that call sites
change by one word instead of by a signature:

| Module | Replaces | Import |
|---|---|---|
| `src/tri/tri_time.zig` | `std.time.timestamp` / `milli` / `micro` / `nanoTimestamp`, `std.time.Timer` | `@import("tri_time")` |
| `src/tri/tri_env.zig` | `std.process.getEnvVarOwned`, `hasEnvVarConstant`, `getEnvMap`, `std.posix.getenv` | `@import("tri_env")` |
| `src/tri/tri_proc.zig` | `std.process.Child.run` | `@import("tri_proc")` |
| `src/tri/tri_io.zig` | the process-wide `Io` handle | `@import("tri_io")` |

`tri_time`, `tri_io` and `tri_proc` are **build modules**, imported by name.
They cannot be path-imported: a single file may not belong to two modules, and
doing so fails with `file exists in modules 'root' and '...'`. If a new module
needs one, add it to that module's `.imports` in `build.zig`.

`tri_env` is a plain path import (`@import("tri_env.zig")`) because all its
users live in `src/tri/`.

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
