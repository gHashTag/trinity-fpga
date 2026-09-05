#!/usr/bin/env python3
"""CAMPAIGN B: what asymmetry costs in silicon.

Method is inherited verbatim from run_synth.py -- yosys 0.65 + nextpnr-xilinx,
xc7a200t, -nodsp where stated, full observation, harness subtraction with an
invariant harness, median of five placement seeds, failures by EXIT CODE.

Two things this file adds over run_synth.py:

  * AREA IS COUNTED AS LOGIC, via logic_count.py on the mapped netlist, because
    nextpnr's SLICE_LUTX is BEL occupancy and subtracting it compares packing
    rather than arithmetic (the defect CODEBOOK_SILICON_2026-08-11 corrects).
    nextpnr is still run -- it supplies placement feasibility and the Fmax
    estimate -- but the LUT numbers quoted come from yosys.

  * THE SUBTRAHEND IS VERIFIED rather than assumed. Every decode arm must show
    exactly 64 + W flip-flops: 64 for the LFSR and one per observed output bit.
    A pruned output bit loses its flip-flop, so this is a direct test that the
    unit under test is fully observed and nothing was optimised away.

CAVEAT on every frequency below, unchanged: bench.xdc's create_clock is not
consumed by nextpnr-xilinx, so "Fmax" is an UNCONSTRAINED post-route
critical-path estimate, not timing closure.
"""
import json, os, sys, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_synth as R
import logic_count as L

MX   = ["mxfp4_decode.v"]
LN   = ["mac_lane.v"]


def _live(vals, W):
    """Output bit positions that are not constant across all sixteen codes."""
    m = [v & ((1 << W) - 1) for v in vals]
    return sum(1 for j in range(W) if len({(v >> j) & 1 for v in m}) == 2)


def _books():
    import gen_asym as G
    e12 = [0, 1, 2, 3, 4, 6, 8, 12]
    e24 = G.e2m1_units()
    n24 = G.near0_units()
    f12 = [0] * 16
    f24 = [0] * 16
    mxb = [0] * 16
    for i, m in enumerate(e12):
        f12[i] = m; f12[8 + i] = -m
    for i, m in enumerate(e24):
        f24[i] = m; f24[8 + i] = -m
        mxb[i] = m; mxb[8 + i] = -m
    mxb[8] = 1
    return {"ad_wire5": 5, "ad_wire6": 6,
            "ad_mxfp4":  _live(f12, 5), "ad_mx12fl": _live(f12, 5),
            "ad_mx24st": _live(f24, 6), "ad_mx24fl": _live(f24, 6),
            "ad_asymmx": _live(mxb, 6), "ad_asymsr": _live(n24, 6)}


LIVE = _books()

# name, W, body, deps, reg_out, nodsp, kind
def arms():
    A = []
    # ---------- 1. decoders alone, each against a bare wire of its width ----
    D = [("ad_wire5",  5, "  assign y = lf[4:0];", []),
         ("ad_mxfp4",  5, "  mxfp4_decode u (.code(lf[3:0]), .w(y));", MX),
         ("ad_mx12fl", 5, "  mx_u12_flat u (.code(lf[3:0]), .w(y));", ["mx_u12_flat.v"]),
         ("ad_wire6",  6, "  assign y = lf[5:0];", []),
         ("ad_mx24st", 6, "  mx_u24_struct u (.code(lf[3:0]), .w(y));", ["mx_u24_struct.v"]),
         ("ad_mx24fl", 6, "  mx_u24_flat u (.code(lf[3:0]), .w(y));", ["mx_u24_flat.v"]),
         ("ad_asymmx", 6, "  asym_mx u (.code(lf[3:0]), .w(y));", ["asym_mx.v"]),
         ("ad_asymsr", 6, "  asym_srt u (.code(lf[3:0]), .w(y));", ["asym_srt.v"])]
    for n, W, b, d in D:
        A.append((n, W, b, d, True, True, "decode"))

    # ---------- 2. one decoder feeding one MAC lane ------------------------
    # LUT-only fabric (-nodsp) and with a DSP48 allowed, so the decode cost is
    # readable as a fraction of a lane rather than in isolation.
    def lane(dec, mod, src, WW):
        if dec is None:
            return (f"  mac_lane #(.WW({WW}),.AW(8),.ACC(32)) u (.clk(clk),.rst_n(rst_n),"
                    f".w(lf[{WW-1}:0]),.a(lf[23:16]),.acc(y));", LN)
        return (f"  wire signed [{WW-1}:0] wv;\n"
                f"  {mod} d (.code(lf[3:0]), .w(wv));\n"
                f"  mac_lane #(.WW({WW}),.AW(8),.ACC(32)) u (.clk(clk),.rst_n(rst_n),"
                f".w(wv),.a(lf[23:16]),.acc(y));", [src] + LN)
    LANES = [("h32",    None, None,            None, None),
             ("raw5",   None, None,            None, 5),
             ("raw6",   None, None,            None, 6),
             ("mxfp4",  "d",  "mxfp4_decode",  "mxfp4_decode.v", 5),
             # The incumbent format implemented the CHEAPEST way it can be, so
             # the lane comparison is not secretly a comparison of coding
             # styles. Without this arm, "asymmetric" and "flat table" are
             # confounded at the lane level exactly as they were at the
             # decoder level.
             ("mx12fl", "d",  "mx_u12_flat",   "mx_u12_flat.v",  5),
             ("mx24fl", "d",  "mx_u24_flat",   "mx_u24_flat.v",  6),
             ("asymmx", "d",  "asym_mx",       "asym_mx.v",      6)]
    for nodsp in (True, False):
        t = "an" if nodsp else "ap"
        for nm, tag, mod, src, WW in LANES:
            if nm == "h32":
                A.append((f"{t}_h32", 32, "  assign y = lf[31:0];", [], True, nodsp, "lane"))
                continue
            b, d = lane(tag, mod, src, WW)
            A.append((f"{t}_{nm}", 32, b, d, False, nodsp, "lane"))
    return A


def one(name, W, body, deps, reg_out, nodsp, kind):
    r = R.run(name, W, body, deps, reg_out, nodsp)
    if "error" in r:
        return r
    r["kind"] = kind
    top = os.path.join(HERE, f"{name}.v")
    lg = L.logic([top] + deps, name, nodsp=nodsp)
    assert not lg["unknown"], (name, lg["unknown"])
    r["logic_lut"]   = lg["lut"]
    r["logic_carry"] = lg["carry"]
    r["logic_ff"]    = lg["ff"]
    r["logic_dsp"]   = lg["dsp"]
    r["logic_muxf"]  = lg["muxf"]
    r["cells"]       = lg["cells"]
    # FULL-OBSERVATION GATE. 64 LFSR bits + one flip-flop per surviving output
    # bit; a pruned output bit takes its flip-flop with it.
    #
    # The bound is 64 + LIVE <= ff <= 64 + W, not equality, and the reason is a
    # measured property of the books rather than slack. Every level of the
    # SYMMETRIC E2M1 book is even, so on the 1/24 grid its LSB is constant zero
    # and pruning it is correct optimisation, not lost observation. The
    # ASYMMETRIC book's +1/24 level is odd, so it is the only book here that
    # uses all six bits. LIVE is computed from the book, so a bit that carries
    # information can never be dropped unnoticed.
    if kind == "decode":
        r["live_bits"] = LIVE.get(name, W)
        r["obs_lo"], r["obs_hi"] = 64 + r["live_bits"], 64 + W
        r["obs_ok"] = r["obs_lo"] <= lg["ff"] <= r["obs_hi"]
    else:
        r["obs_ok"] = None
    return r


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    A = [a for a in arms() if not only or a[0].startswith(only)]
    print(f"{len(A)} arms, 5 placement seeds each", flush=True)
    res = {}
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        for fu in cf.as_completed({ex.submit(one, *a): a[0] for a in A}):
            r = fu.result()
            res[r["name"]] = r
            if "error" in r:
                print(f"{r['name']:10s} ERROR {r['error']}", flush=True)
            else:
                ob = {True: "obs-ok", False: "OBS-FAIL", None: "-"}[r["obs_ok"]]
                print(f"{r['name']:10s} logicLUT={r['logic_lut']:5d} CY4={r['logic_carry']:4d} "
                      f"FF={r['logic_ff']:4d} DSP={r['logic_dsp']:2d} "
                      f"BEL_LUTX={r.get('lut',0):5d} Fmed={r.get('fmed',0):8.2f} "
                      f"spread={100*r.get('fspread',0):5.1f}% {ob}", flush=True)
            json.dump(res, open(os.path.join(HERE, "results_asym.json"), "w"), indent=1)
    bad = [k for k, v in res.items() if v.get("obs_ok") is False]
    print("FULL OBSERVATION:", "PASS" if not bad else f"FAIL {bad}")
