#!/usr/bin/env python3
"""The last estimated number in the selection table: gradient span.

Every other span there is measured -- within-block 3.04 binades, whole weight
13.4, accumulator 13.9. The gradient row said "~40, from the literature", which
is the only figure in the table not from this tree.

One backward pass on the model already used for every other weight measurement,
so the object is the same one.
"""
import os, math, sys
import numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL, SEQLEN = os.path.join(W, "smollm2"), 512

def load_wikitext():
    import pyarrow.parquet as pq
    t = pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
    return "\n\n".join(t.column("text").to_pylist())

print("загружаю модель…", flush=True)
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
model.train()
ids = tok(load_wikitext()[:20000], return_tensors="pt").input_ids[:, :SEQLEN]
out = model(ids, labels=ids)
out.loss.backward()
print(f"loss = {out.loss.item():.4f}\n", flush=True)

spans, allg = [], []
for n, p in model.named_parameters():
    if p.grad is None or p.dim() != 2 or "lm_head" in n: continue
    g = p.grad.detach().abs().double()
    g = g[g > 0]
    if g.numel() < 100: continue
    gs = g if g.numel() <= 2_000_000 else g[torch.randperm(g.numel())[:2_000_000]]
    lo = torch.quantile(gs, 0.001).item(); hi = g.max().item()
    if lo <= 0: continue
    spans.append(math.log2(hi / lo))
    allg.append(g.flatten()[::101].numpy())

sp = np.array(spans)
g = np.concatenate(allg)
print(f"слоёв с градиентом: {len(sp)}")
print(f"\nРАЗМАХ ГРАДИЕНТА ПО СЛОЮ (0.1-й процентиль → максимум), бинад:")
for q in (50, 90, 99):
    print(f"   {q:2d}-й процентиль по слоям: {np.percentile(sp, q):6.2f}")
print(f"   максимум по слоям        : {sp.max():6.2f}")
lo, hi = np.percentile(g, 0.1), g.max()
print(f"\nРАЗМАХ ПО ВСЕЙ МОДЕЛИ СРАЗУ: {math.log2(hi/lo):.2f} бинад")
print(f"\nв таблице выбора стояло: ~40 бинад (из литературы)")
m = np.median(sp)
print(f"измерено (медиана по слоям): {m:.2f} бинад — "
      f"{'оценка ЗАВЫШАЛА' if m < 40 else 'оценка занижала'} в {40/m:.1f} раза"
      if m < 40 else f"измерено {m:.2f}")
