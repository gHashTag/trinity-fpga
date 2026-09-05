
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
