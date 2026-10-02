#!/usr/bin/env bash
# Materialise the sibling namespaces check_doc_refs.py resolves against.
#
# check_doc_refs.py looks for sibling repositories next to this one
# (ROOT.parent / name). CI has no siblings, so without this every reference
# that resolves only there reads as rot. Two workflows need them: doc-refs.yml
# runs the checker, and gates-can-fail.yml runs it with a defect injected.
# The second one did not materialise them, so check_doc_refs was red on a
# clean tree there and the harness reported it UNTESTABLE -- the gate was never
# shown to be able to fail. One script, called by both, so the two cannot
# drift apart again.
#
# The sibling list is read from the checker itself (SIBLING_NAMES), not copied
# here: a third copy of that list is how the two workflows diverged.
#
# NAMES ONLY, NOT CONTENT. The checker asks one question of a sibling -- does
# this path exist -- so each sibling is cloned blobless and no-checkout, its
# file list read with `git ls-tree`, and empty files created at those paths.
# Nothing is fabricated that the checker inspects: it never opens a sibling
# file, only tests for one.
#
#   tools/materialise_siblings.sh [dest]    dest defaults to the repo's parent
set -uo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
dest=${1:-$(dirname "$here")}
export GIT_TERMINAL_PROMPT=0   # a private sibling must fail fast, not ask

names=$(python3 - "$here/tools/check_doc_refs.py" <<'EOF'
import ast, sys
tree = ast.parse(open(sys.argv[1]).read())
for node in tree.body:
    if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "SIBLING_NAMES" for t in node.targets):
        print("\n".join(ast.literal_eval(node.value)))
        break
else:
    sys.exit("SIBLING_NAMES not found in check_doc_refs.py")
EOF
) || { echo "::error::cannot read SIBLING_NAMES from tools/check_doc_refs.py"; exit 1; }

cd "$dest" || exit 1
for s in $names; do
  if [ -e "$s" ] && [ ! -d "$s.git" ]; then
    echo "$s: already present at $dest/$s -- left as is"
    continue
  fi
  if [ -d "$s.git" ] || git clone -q --filter=blob:none --no-checkout --depth 1 \
       "https://github.com/gHashTag/$s" "$s.git" 2>/dev/null; then
    n=0
    while IFS= read -r p; do
      mkdir -p "$s/$(dirname "$p")" && : > "$s/$p" && n=$((n+1))
    done < <(git -C "$s.git" ls-tree -r --name-only HEAD)
    echo "$s: $n paths"
  else
    echo "$s: UNREACHABLE (private or gone) -- references resolving only there read as dangling"
  fi
done
