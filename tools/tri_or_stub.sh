#!/usr/bin/env bash
# Run one `tri` subcommand in CI and tell a stub from a breakage.
#
#   tools/tri_or_stub.sh stress --health
#
# Several brain subcommands (`tri stress ...`, issue 768) are still stubs that
# print "not implemented" and exit non-zero. The workflow used to meet that in
# one of two dishonest ways: `|| true`, which also swallowed a crash, a panic
# and a binary that was never built; or no guard at all, which made a job red
# forever for a command nobody has written yet. For weeks the binary was in fact
# never built -- `zig build tri` RUNS the CLI and installs nothing -- and every
# `|| true` hid it.
#
# So: success passes, a declared stub is a notice, anything else fails.
set -uo pipefail

TRI="${TRI:-./zig-out/bin/tri}"
if [ ! -x "$TRI" ]; then
  echo "::error::$TRI does not exist -- build it with 'zig build tri-compile', not 'zig build tri' (that step runs the CLI and installs nothing)" >&2
  exit 1
fi

out=$("$TRI" "$@" 2>&1)
rc=$?
printf '%s\n' "$out"
[ "$rc" -eq 0 ] && exit 0

if printf '%s' "$out" | grep -qiE 'not implemented|NotImplemented'; then
  echo "::notice::tri $* is a stub that says so (issue 768) -- not measured, not failed" >&2
  exit 0
fi
echo "::error::tri $* exited $rc and is not a declared stub" >&2
exit "$rc"
