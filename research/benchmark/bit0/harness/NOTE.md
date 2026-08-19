# These shell scripts are archived evidence, not tooling

This repository has a standing rule against shell scripts
(`.claude/rules/no-shell-scripts.md`): new tooling is added as `tri` subcommands
or Zig binaries, and the legacy `.sh` files elsewhere in the tree are marked for
deletion. **The three scripts in this directory are a deliberate, narrow
exemption.** This file records why, so the exemption is auditable rather than
silent — and so nobody later reads their presence as the rule having lapsed.

## Why they are here

`bench-openxc7.sh`, `bench.sh` and `vivado-nonet.sh` produced the measurements
in `../openxc7/` and `../vivado/`. They ran on **bit0**, a machine outside this
project, against a **frozen** toolchain, in a campaign that is finished and will
not be re-run in place.

They are kept for one reason: without them the published numbers have no
reproduction path. A benchmark that reports 13.7× and cannot say precisely what
it timed is an assertion, not a measurement. Rewriting them in Zig after the
fact would produce a *different* harness and would silently break the link
between the artefacts and the thing that made them — which is the one property
they exist to carry.

The same reasoning is why `../vivado/contaminated-v1/` is kept: evidence of how
a number was produced outranks tidiness, including when the number was wrong.

## What this exemption does not cover

The rule's specific warning is against copying patterns from legacy scripts, and
that risk is live here. So, explicitly:

- **Do not source, call, or import these from anything** — not `src/`, not
  `build.zig`, not a `tri` subcommand, not a GitHub Actions step.
- **Do not use them as a template.** `vivado-nonet.sh` in particular is a
  `unshare -r -n` wrapper built to defeat a Flexera telemetry stall on one
  vendor toolchain on one machine. It solves a problem this project does not
  otherwise have, in a way this project does not otherwise sanction.
- **Do not extend them.** If a further campaign is needed, the harness for it
  belongs in Zig, and this directory stays as the record of the campaign that
  preceded it.

Treat this directory the way you would treat a scanned lab notebook: readable,
citable, and not executable infrastructure.

## Provenance

Delivered by @cavearr in #613 alongside the CSVs they produced. Merged as
delivered; this note was added afterwards rather than by editing the
contributor's branch, so the measurement record stays exactly as it was handed
over.
