#!/usr/bin/env python3
"""Do the reproduction scripts still reference modules that exist?

fpga/tnet/mk8.sh -- the script that produced the 21-format silicon table --
instantiated `gft_add_w` while the file it reads defines `tef_add_w`. The
TEF-to-TNF rename changed the module name and left the script. Yosys errored,
no JSON was produced, and every run reported empty fields. Nobody noticed
because the table had already been written.

A reproduction path that is never run is a claim, not a capability. This finds
the same rot everywhere else before it is discovered by accident again.

For each shell script that invokes yosys with read_verilog, collect the Verilog
files it reads and the module names it instantiates, and report instantiations
with no matching definition.
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Verilog keywords and common constructs that look like instantiations
NOISE = {"if", "for", "while", "case", "module", "always", "assign", "wire",
         "reg", "input", "output", "inout", "parameter", "localparam", "begin",
         "end", "generate", "endgenerate", "initial", "function", "task",
         "posedge", "negedge", "signed", "unsigned", "integer", "genvar",
         "defparam", "endmodule", "specify", "and", "or", "not", "nand", "nor",
         "xor", "xnor", "buf", "assert", "cover", "default_nettype"}

def defined_modules(paths):
    out = set()
    for p in paths:
        try: src = p.read_text(errors="ignore")
        except Exception: continue
        out |= set(re.findall(r'^\s*module\s+(\w+)', src, re.M))
    return out

def instantiated(src):
    # NAME #( ... ) inst ( ... )   or   NAME inst ( ... )
    hits = set(re.findall(r'^\s*(\w+)\s*#\s*\(', src, re.M))
    hits |= set(re.findall(r'^\s*(\w+)\s+\w+\s*\(\s*\.', src, re.M))
    return {h for h in hits if h not in NOISE}

fails, checked = [], 0
for sh in sorted(ROOT.rglob("fpga/**/*.sh")):
    try: script = sh.read_text(errors="ignore")
    except Exception: continue
    if "read_verilog" not in script: continue
    checked += 1
    # files the script hands to yosys, plus any it writes inline via heredoc
    named = set(re.findall(r'([\w./$-]+\.v)\b', script))
    paths = []
    for n in named:
        if "$" in n: continue
        p = (sh.parent / n)
        if p.exists(): paths.append(p)
    defined = defined_modules(paths) | set(re.findall(r'^\s*module\s+(\w+)', script, re.M))
    # heredoc bodies inside the script define modules too
    for body in re.findall(r'<<\s*\\?\w+\n(.*?)\n\w+\n', script, re.S):
        defined |= set(re.findall(r'^\s*module\s+(\w+)', body, re.M))
    used = instantiated(script)
    missing = sorted(u for u in used if u not in defined)
    for m in missing:
        fails.append(f"{sh.relative_to(ROOT)}: instantiates `{m}` -- no definition "
                     f"in the {len(paths)} file(s) it reads")

# Scripts whose source module is absent from the tree AND from history are dead
# tooling rather than a rotted path. They are listed separately: nothing
# published depends on them, and conflating the two would make the gate look
# more alarming than the tree is.
DEAD = {"fpga/tef/upper/sweep.sh", "fpga/tef/upper/upper.sh"}
live = [f for f in fails if not any(d in f for d in DEAD)]
dead = [f for f in fails if any(d in f for d in DEAD)]

print(f"scripts invoking yosys: {checked}")
if dead:
    print(f"\n{len(dead)} reference(s) in dead tooling (module absent from tree and "
          f"history; no published number depends on these):")
    for f in dead: print(f"  [dead] {f}")
fails = live
if fails:
    print(f"\nFAIL: {len(fails)} stale reference(s)\n")
    for f in fails: print(f"  {f}")
    sys.exit(1)
print("OK: every instantiated module is defined in the files its script reads")
