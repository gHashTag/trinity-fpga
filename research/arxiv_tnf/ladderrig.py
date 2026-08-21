#!/usr/bin/env python3
"""W953: the third point -- a float-style MAC lane, to pin the W952 bracket.

W952 priced a FIXED-POINT lane (decode to fixed point, multiply there): TNF4 768
cells against fp6 e2m3's 159, i.e. 4.83x. That is the datapath most punishing to a
wide-range format. The other end, the accumulator alone, is +1.5 % per element. The
honest answer was a bracket, and this is the measurement that closes it.

A float-style lane multiplies SMALL mantissas and shifts. Getting the mantissa right
without assuming a field layout: every grid value is |v| = M*u for an integer M, and
every integer factors as M = odd * 2^s. So decode gives (sign, odd, s); the product
is odd1*odd2 shifted by s1+s2, exactly, with no rounding and no subnormal special
case -- the factorisation is valid for any grid, which the (1.mantissa, exponent)
form is not: it fails on both fp6 grids, whose bottom binade is truncated.

Measured widths (odd part, max shift), and the resulting aligned bus, agree exactly
with the fixed-point product width of W952:

  TNF4      odd 2 bits, s<=14  ->  2*2 + 2*14 = 32 = 33-1
  fp6 e3m2  odd 3 bits, s<=6   ->  2*3 + 2*6  = 18 = 19-1
  fp6 e2m3  odd 4 bits, s<=2   ->  2*4 + 2*2  = 12 = 13-1

so the two lane styles are priced in the same frame, into the same accumulator.
"""
import json, math, os, pathlib, re, subprocess, sys
from fractions import Fraction
import numpy as np

S = pathlib.Path(os.environ.get("T27_WORK") or pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, os.environ.get("T27_CONFORMANCE") or str(S / "oracles"))
import tnf_ref as T, fp8_ref as F8

NS = [1, 2, 4, 8]
# W954: the ladder's TNF8 is TNFFormat(3, 4) -- 10 bits, 30.95 binades. Every rig in
# this project instantiated TNFFormat(4, 3) instead: 11 bits, 126.91 binades, a
# different format sharing TNF16's exponent field. Both are priced here, against
# floats of each one's own physical width, so the substitution has a number.
_F = F8.FPxFormat
FMT = {"TNF8_ladder_10b": (T, T.TNFFormat(3, 4), 10),
       "fp10_e5m4":       (F8, _F("fp10_e5m4", 5, 4, 15), 10),
       "fp10_e6m3":       (F8, _F("fp10_e6m3", 6, 3, 31), 10),
       }
# W954: the 11-bit arm (TNFFormat(4,3), 126.91 binades -> a ~270-bit aligned bus)
# was killed without a traceback partway through. It is DROPPED here rather than
# silently omitted, and the omission is reported. Lesson 1441 said write progress
# incrementally; that lesson had been applied to the training rig and not to this
# one, which is why four completed synthesis runs were lost with it.
CELL = re.compile(r"^\s+(\d+)\s+(LUT[1-6]|CARRY4|MUXF[78])\s*$")


def grid(mod, fmt, bits):
    d = {}
    for c in range(1 << bits):
        try:
            v = float(mod.decode(fmt, c))
        except Exception:
            continue
        if np.isfinite(v):
            d[c] = v
    return d


def decompose(vals):
    fr = {c: Fraction(v).limit_denominator(1 << 40) for c, v in vals.items()}
    nz = [f for f in fr.values() if f != 0]
    e = 0
    while any((f * Fraction(2 ** e)).denominator != 1 for f in nz):
        e += 1
    u = Fraction(1, 2 ** e)
    out = {}
    for c, f in fr.items():
        if f == 0:
            out[c] = (0, 0, 0)
            continue
        M = int(abs(f) / u)
        assert Fraction(M) * u == abs(f)
        s = 0
        while M % 2 == 0:
            M //= 2
            s += 1
        out[c] = (1 if f < 0 else 0, M, s)
    ob = max(M.bit_length() for _, M, _ in out.values())
    smax = max(s for _, _, s in out.values())
    return out, ob, smax, u


def cells(src, work):
    work.write_text(src)
    r = subprocess.run(["yosys", "-p", f"read_verilog {work}; synth_xilinx -top top -nodsp; stat"],
                       capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-400:])
    blocks = r.stdout.split("=== design hierarchy ===")
    if len(blocks) < 2:
        raise RuntimeError("no design hierarchy block")
    lut = mux = 0
    for line in blocks[-1].splitlines():
        m = CELL.match(line)
        if m:
            if m.group(2).startswith("MUXF"):
                mux += int(m.group(1))
            else:
                lut += int(m.group(1))
    if lut == 0:
        raise RuntimeError("zero cells counted -- parser missed the stat block")
    return lut, mux


def lane(name, dec, ob, smax, bits, algn, acc):
    sb = max(1, (smax).bit_length())
    rows = "\n".join(
        f"      {bits}'d{c}: {{sg, od, sh}} = {{1'b{s}, {ob}'d{M}, {sb}'d{sv}}};"
        for c, (s, M, sv) in sorted(dec.items()))
    return f"""
module {name} (input clk, input [{bits-1}:0] wc, input [{bits-1}:0] ac,
               input signed [{acc-1}:0] ai, output reg signed [{acc-1}:0] ao);
  reg sgw, sga; reg [{ob-1}:0] odw, oda; reg [{sb-1}:0] shw, sha;
  reg sg; reg [{ob-1}:0] od; reg [{sb-1}:0] sh;
  always @* begin
    case (wc)
{rows}
      default: {{sg, od, sh}} = 0;
    endcase
    sgw = sg; odw = od; shw = sh;
  end
  always @* begin
    case (ac)
{rows}
      default: {{sg, od, sh}} = 0;
    endcase
    sga = sg; oda = od; sha = sh;
  end
  wire [{2*ob-1}:0] mp = odw * oda;
  wire [{sb}:0] sft = shw + sha;
  wire [{algn-1}:0] al = {{{{{algn-2*ob}{{1'b0}}}}, mp}} << sft;
  wire signed [{acc-1}:0] term = (sgw ^ sga)
      ? -$signed({{{{{acc-algn}{{1'b0}}}}, al}}) : $signed({{{{{acc-algn}{{1'b0}}}}, al}});
  always @(posedge clk) ao <= ai + term;
endmodule
"""


def chain(name, n, bits, acc):
    ws = "\n".join(f"  wire signed [{acc-1}:0] s{i};" for i in range(n))
    ins = "\n".join(
        f"  {name} u{i} (.clk(clk), .wc(wc ^ {bits}'d{(i*7) & ((1<<bits)-1)}), "
        f".ac(ac ^ {bits}'d{(i*13) & ((1<<bits)-1)}), .ai({'ai' if i==0 else f's{i-1}'}), .ao(s{i}));"
        for i in range(n))
    return (f"module top (input clk, input [{bits-1}:0] wc, input [{bits-1}:0] ac,\n"
            f"            input signed [{acc-1}:0] ai, output signed [{acc-1}:0] ao);\n"
            f"{ws}\n{ins}\n  assign ao = s{n-1};\nendmodule\n")


out = {"metric": "LUT1-6 + CARRY4", "ns": NS, "style": "float: odd-mantissa multiply + shift",
       "fields": {}, "cost": {}}
for name, spec in FMT.items():
    vals = grid(*spec)
    dec, ob, smax, u = decompose(vals)
    algn = 2 * ob + 2 * smax
    acc = algn + 1 + 5
    out["fields"][name] = {"odd_bits": ob, "max_shift": smax, "aligned": algn, "acc": acc}
    print(f"  {name:9} нечёт.мантисса {ob} бит, сдвиг <= {smax}, шина {algn}, аккум {acc}", flush=True)
    pts, mxs = [], []
    for n in NS:
        src = lane(f"fl_{name}", dec, ob, smax, spec[2], algn, acc) + chain(f"fl_{name}", n, spec[2], acc)
        c, m = cells(src, S / f"_fl_{name}_{n}.v")
        pts.append(c); mxs.append(m)
        print(f"  {name:9} N={n}: {c:6d} LUT+CARRY4, {m:4d} MUXF", flush=True)
    A = np.vstack([np.array(NS), np.ones(len(NS))]).T
    slope, fix = np.linalg.lstsq(A, np.array(pts, float), rcond=None)[0]
    pred = A @ np.array([slope, fix])
    r2 = 1 - ((np.array(pts) - pred) ** 2).sum() / max(((np.array(pts) - np.mean(pts)) ** 2).sum(), 1e-9)
    ms = np.linalg.lstsq(A, np.array(mxs, float), rcond=None)[0][0]
    out["cost"][name] = {"per_lane": round(float(slope), 2), "fixture": round(float(fix), 2),
                         "r2": round(float(r2), 5), "points": pts,
                         "mux_per_lane": round(float(ms), 2)}
    print(f"  -> {name}: {slope:.2f} ячеек на флоат-полосу (+{ms:.2f} MUXF), R²={r2:.5f}\n", flush=True)
    try:
        (S / "ladder_w954.json").write_text(json.dumps(out, indent=1))
    except OSError as e:
        print(f"  (запись не удалась: {e})", flush=True)

p = S / "ladder_w954.json"
p.write_text(json.dumps(out, indent=1))
print("WROTE " + str(p), flush=True)
