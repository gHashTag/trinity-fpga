# No Shell Scripts

## Rule
**NEVER create, edit, or reference .sh/.bash files.** Trinity is pure Zig — zero bash, zero Python.

## What to do instead
- Need a CLI tool? → Add a `tri` subcommand in Zig
- Need a deploy entrypoint? → Zig binary (see `src/cli/entrypoint_train.zig`)
- Need a build step? → `build.zig` step
- Need a CI action? → Zig binary called from GitHub Actions YAML
- Need data prep? → Zig tool in `src/cli/` or `tools/`

## Existing .sh files
Legacy scripts in `scripts/`, `deploy/`, `.ralph/scripts/`, `fpga/` are marked for deletion.
Do NOT use them. Do NOT reference them. Do NOT copy patterns from them.

## The one exemption: archived measurement provenance

`research/benchmark/**/harness/` may retain the `.sh` files that produced a
published measurement. They are evidence, not tooling — the reproduction path
for numbers this project quotes publicly, run on external machines against
frozen toolchains, in campaigns that are finished.

Rewriting them in Zig after the fact would produce a *different* harness and
break the link between the artefacts and the thing that made them, which is the
only property they exist to carry. Deleting them leaves published numbers
unreproducible.

The exemption is narrow and does not soften anything above: these files must not
be sourced, called, imported, extended, or used as a template, and each such
directory carries a `NOTE.md` saying so. A new campaign gets a Zig harness; the
old directory stays as the record.

**Do not include this path in any sweep that deletes `.sh` files.**

## Dockerfile rules
- Runtime stage: NO `bash`, NO `python3`, NO `sh` in RUN commands
- Entrypoints: ONLY Zig binaries (`ENTRYPOINT ["/usr/local/bin/some-zig-binary"]`)
- Build stage: minimal `sh` allowed ONLY for `apt-get` and `tar` (unavoidable in Docker)

## Enforcement
PreToolUse hook blocks creation of .sh files.
