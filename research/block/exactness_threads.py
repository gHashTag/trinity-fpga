"""The reordering that actually happens to people: a different thread count.

exactness_payoff.py permutes the contraction axis on purpose. That is the clean experiment,
but nobody permutes their weights by accident. What DOES vary between two honest runs of the
same script is how the BLAS splits the reduction -- and the first thing that changes it is the
number of threads. Same weights, same data, same code, different machine: different sum order.

So this runs the identical phi^k-quantised model at 1, 2, 4 and 8 threads and reports the
perplexity spread. It is the reproducibility hazard in the units the campaign reports its
margins in, with no artificial permutation anywhere.

Self-tested before any number: the weights must be bitwise identical across arms, and a
thread-count change must be shown to actually move a GEMM (otherwise there is nothing here).
"""
import os
import sys
import json
import time
import hashlib
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WDIR = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
        "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
PY = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
      "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/ppl-venv/bin/python")

CHILD = r'''
import os, sys, json, hashlib
import numpy as np, torch, torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
WDIR, TAG, NW, TH = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
torch.set_grad_enabled(False); torch.set_num_threads(TH)
K, SEQLEN = 32, 2048
PHI = (1+5**0.5)/2; LOGPHI = np.log(PHI)
PHIL = torch.tensor([0.0]+[PHI**(-k) for k in range(6,-1,-1)], dtype=torch.float64)
def quant_phi(w):
    n = (w.shape[1]//K)*K
    b = w[:, :n].reshape(-1, K).double()
    amax = b.abs().amax(dim=1).clamp(min=1e-300)
    s = torch.pow(PHI, torch.ceil(torch.log(amax)/LOGPHI - 1e-9))
    a = (b/s[:, None]).abs()
    rec = torch.sign(b)*PHIL[torch.bucketize(a, (PHIL[:-1]+PHIL[1:])/2)]*s[:, None]
    out = w.clone(); out[:, :n] = rec.reshape(-1, n); return out
M = os.path.join(WDIR, TAG)
tok = AutoTokenizer.from_pretrained(M)
import pyarrow.parquet as pq
t = "\n\n".join(pq.read_table(os.path.join(WDIR,"wikitext2-test.parquet")).column("text").to_pylist())
ids = tok(t, return_tensors="pt").input_ids[0]
n = (ids.numel()//SEQLEN)*SEQLEN
X = ids[:n].reshape(-1, SEQLEN)[:NW]
m = AutoModelForCausalLM.from_pretrained(M, dtype=torch.float32); m.eval()
tg = [(nm, md) for nm, md in m.named_modules()
      if isinstance(md, torch.nn.Linear) and "lm_head" not in nm and "embed_out" not in nm]
h = hashlib.sha256()
for nm, md in tg:
    md.weight.data = quant_phi(md.weight.data.double()).float()
    h.update(md.weight.data.numpy().tobytes())
# probe: does THIS thread count give a different GEMM than a fixed reference order?
g = torch.Generator().manual_seed(3)
xf = torch.randn(256, 2048, generator=g); wf = torch.randn(2048, 2048, generator=g)
probe = hashlib.sha256(F.linear(xf, wf).numpy().tobytes()).hexdigest()[:16]
tot = 0.0
for i in range(X.shape[0]):
    c = X[i:i+1]; tot += m(c, labels=c).loss.double().item()
print("RESULT " + json.dumps({"threads": TH, "ppl": float(np.exp(tot/X.shape[0])),
      "weight_sha": h.hexdigest()[:16], "gemm_sha": probe,
      "torch_threads": torch.get_num_threads()}))
'''

TAG = sys.argv[1] if len(sys.argv) > 1 else "smollm2"
NW = int(sys.argv[2]) if len(sys.argv) > 2 else 40
THREADS = [1, 2, 4, 8]

child = os.path.join(HERE, "_thr_child.py")
open(child, "w").write(CHILD)

rows = []
for th in THREADS:
    t0 = time.time()
    env = dict(os.environ, OMP_NUM_THREADS=str(th), MKL_NUM_THREADS=str(th))
    out = subprocess.run([PY, child, WDIR, TAG, str(NW), str(th)],
                         capture_output=True, text=True, env=env)
    line = [l for l in out.stdout.splitlines() if l.startswith("RESULT ")]
    if not line:
        print(out.stdout[-3000:], out.stderr[-3000:])
        sys.exit(f"child failed at threads={th}")
    r = json.loads(line[0][7:])
    r["seconds"] = round(time.time() - t0, 1)
    rows.append(r)
    print(f"    threads {th}: ppl = {r['ppl']:13.7f}   weights {r['weight_sha']}  "
          f"gemm {r['gemm_sha']}  ({r['seconds']}s)", flush=True)

# ---- self-tests, AFTER collection but BEFORE any conclusion is printed
shas = {r["weight_sha"] for r in rows}
if len(shas) != 1:
    sys.exit(f"SELF-TEST FAILED: weights differ across arms {shas} -- not an order-only test")
print(f"\n  S1 all {len(rows)} arms hold BITWISE identical phi^k weights "
      f"({rows[0]['weight_sha']})  OK")
got = {r["threads"]: r["torch_threads"] for r in rows}
if got != {t: t for t in THREADS}:
    sys.exit(f"SELF-TEST FAILED: thread count not actually applied: {got}")
print(f"  S2 torch.get_num_threads() matches the request in every arm {got}  OK")
gs = {r["gemm_sha"] for r in rows}
print(f"  S3 reference-GEMM hashes across thread counts: {len(gs)} distinct "
      f"{'-- thread count DOES change the reduction' if len(gs) > 1 else '-- identical'}")

p = [r["ppl"] for r in rows]
print(f"\n  {TAG}, {NW} windows, phi^k weights, ONLY the thread count differs")
print(f"  spread = {max(p)-min(p):.7f} ppl   sd = {np.std(p, ddof=1):.7f}")
print(f"  campaign margins: phi-vs-2^k Qwen 0.0935 / SmolLM2 1.145")
json.dump({"tag": TAG, "windows": NW, "rows": rows, "spread": max(p) - min(p),
           "sd": float(np.std(p, ddof=1)),
           "distinct_gemm_hashes": len(gs), "weights_identical": len(shas) == 1},
          open(os.path.join(HERE, f"exactness_threads_{TAG}.json"), "w"), indent=1)
