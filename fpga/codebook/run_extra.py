#!/usr/bin/env python3
"""B=6 arms: the width the perplexity gate selects."""
import json, os, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_synth import run, HERE
SP = ("  wire [127:0] cds = {lf[63:0], lf[63:0]} ^ {64'h0F0F_0F0F_0F0F_0F0F, lf[31:0], lf[63:32]};\n"
      "  wire [255:0] act = {cds, cds} ^ {128'h0, lf[63:0], lf[63:0]};\n")
A = [
 ("mn_cb6", 32,
  "  mcm_lane_cb6 #(.AW(8),.ACC(32)) u (.clk(clk),.rst_n(rst_n),"
  ".code(lf[3:0]),.a(lf[23:16]),.acc(y));", ["mcm_lane.v"], False, True),
 ("b_cb6", 40, SP +
  "  blk32_cb6 u (.clk(clk),.rst_n(rst_n),.codes(cds),.acts(act),"
  ".e8m0(lf[39:32]),.emax(lf[47:40]),.y(y));",
  ["blk32.v", "blk_scale.v", "mxfp4_decode.v", "cb4_decode_b10.v", "cb4_decode_b6.v"], False, True),
]
res = {}
with cf.ThreadPoolExecutor(max_workers=2) as ex:
    for fu in cf.as_completed({ex.submit(run, *a): a[0] for a in A}):
        r = fu.result(); res[r["name"]] = r
        print(r if "error" in r else
              f"{r['name']:12s} LUT={r.get('lut',0):5d} FF={r.get('ff',0):5d} "
              f"CARRY={r.get('carry',0):4d} DSP={r.get('dsp',0):3d} "
              f"Fmed={r.get('fmed',0):8.2f} spread={100*r.get('fspread',0):5.1f}%", flush=True)
        json.dump(res, open(os.path.join(HERE, "results_extra.json"), "w"), indent=1)
