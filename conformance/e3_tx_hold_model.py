#!/usr/bin/env python3
"""E3 transmit edge timing in nextpnr-xilinx's own delay model, for the routed e3z netlist.

Pre-registered in specs/trinet/e3_tx_hold_model_ax7203.t27 (constants from e3_tx_hold_params.py,
which e3_tx_hold_from_spec.mjs writes from it). The spec has the check, the prediction and what the
result does not say; this file only carries it out.

nextpnr-xilinx re-places and re-routes e3z's synthesized netlist with e3z's own arguments plus --sdf.
The run counts as e3z only if its FASM equals e3z's. The SDF is then walked back from the input pin
of each TX pad's output buffer to a flip-flop: net delays (INTERCONNECT), LUT pin-to-output delays
and clock-to-Q (IOPATH), and the clock net's delay into that flip-flop's clock pin. The clock source
is common to all seven flip-flops and cancels. Hold uses the smallest delays of the data path against
the largest of the clock path and setup the other way round; nextpnr-xilinx writes one number per arc
(DelayInfo has a single delay), so both are the same number here.

    python3 conformance/e3_tx_hold_model.py              # the run; exit 0 PASS, 1 FAIL, 2 NO VERDICT
    python3 conformance/e3_tx_hold_model.py --self-test  # parser and walk on a synthetic SDF; no tools
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from e3_tx_hold_params import SPEC as S, SPEC_FILE, SPEC_SHA256  # noqa: E402

LOG = os.path.join(HERE, 'model_runs', 'e3_tx_hold_model.log')


class NoVerdict(Exception):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for blk in iter(lambda: fh.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def expand(p):
    return os.path.expanduser(p)


# ---- SDF ---------------------------------------------------------------------------------------

TOKEN = re.compile(r'\(|\)|"(?:[^"]|"")*"|(?:\\.|[^\s()"])+')


def parse_sexpr(text):
    """Nested lists of atoms. A backslash escapes the next character (nextpnr's escape_name)."""
    stack, cur = [], []
    for m in TOKEN.finditer(text):
        t = m.group(0)
        if t == '(':
            stack.append(cur)
            cur = []
        elif t == ')':
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif t.startswith('"'):
            cur.append(t[1:-1].replace('""', '"'))
        else:
            cur.append(re.sub(r'\\(.)', r'\1', t))
    if stack or len(cur) != 1:
        raise NoVerdict('SDF: unbalanced parentheses')
    return cur[0]


def delay(rise_fall):
    """[['a:b:c'], ['d:e:f']] -> (smallest, largest) over rise and fall, min and max."""
    vals = []
    for group in rise_fall:
        if len(group) != 1:
            raise NoVerdict(f'SDF: delay {group!r}')
        vals += [float(x) for x in group[0].split(':')]
    return min(vals), max(vals)


def read_sdf(text):
    """-> (interconnect {(to_cell, to_port): (from_cell, from_port, (lo, hi))},
           iopath {(cell, from, to): (lo, hi)}, celltype {cell: type})"""
    root = parse_sexpr(text)
    if not root or root[0] != 'DELAYFILE':
        raise NoVerdict('SDF: no DELAYFILE')
    head = {x[0]: x[1:] for x in root[1:] if isinstance(x, list) and x and x[0] != 'CELL'}
    if head.get('TIMESCALE') != ['1ps']:
        raise NoVerdict(f"SDF: TIMESCALE {head.get('TIMESCALE')}, want 1ps")
    ic, iop, ctype = {}, {}, {}
    for cell in (x for x in root[1:] if isinstance(x, list) and x and x[0] == 'CELL'):
        f = {x[0]: x[1:] for x in cell[1:]}
        inst = f['INSTANCE'][0] if f['INSTANCE'] else ''
        ctype[inst] = f['CELLTYPE'][0]
        for d in f.get('DELAY', []):
            for arc in d[1:]:                      # d = ['ABSOLUTE', arcs...]
                if arc[0] == 'INTERCONNECT':
                    fc, fp = arc[1].rsplit('/', 1)
                    tc, tp = arc[2].rsplit('/', 1)
                    if (tc, tp) in ic:
                        raise NoVerdict(f'SDF: two drivers into {tc}/{tp}')
                    ic[(tc, tp)] = (fc, fp, delay(arc[3:]))
                elif arc[0] == 'IOPATH':
                    iop[(inst, arc[1], arc[2])] = delay(arc[3:])
    return ic, iop, ctype


# ---- the walk ----------------------------------------------------------------------------------

def arcs_into(iop, cell, out):
    return sorted((k[1], v) for k, v in iop.items() if k[0] == cell and k[2] == out)


def walk_to_ff(ic, iop, ctype, cell, port, luts_left):
    """From input pin (cell, port) back through single-input LUTs to a flip-flop.
    -> dict(ff, lo, hi, luts, route, lut, clk, c2q)"""
    lo = hi = 0.0
    parts = dict(route=0.0, lut=0.0, luts=[])
    while True:
        if (cell, port) not in ic:
            raise NoVerdict(f'no INTERCONNECT into {cell}/{port}')
        dc, dp, (a, b) = ic[(cell, port)]
        lo, hi, parts['route'] = lo + a, hi + b, parts['route'] + b
        t = ctype.get(dc)
        if t == 'SLICE_FFX':
            if (dc, 'CK', dp) not in iop:
                raise NoVerdict(f'no clock-to-Q IOPATH CK -> {dp} in {dc}')
            a, b = iop[(dc, 'CK', dp)]
            lo, hi, parts['c2q'] = lo + a, hi + b, b
            if (dc, 'CK') not in ic:
                raise NoVerdict(f'no clock INTERCONNECT into {dc}/CK')
            src_c, src_p, (a, b) = ic[(dc, 'CK')]
            lo, hi, parts['clk'] = lo + a, hi + b, b
            return dict(parts, ff=dc, clk_src=(src_c, src_p), lo=lo, hi=hi)
        if t != 'SLICE_LUTX':
            raise NoVerdict(f'{dc} is {t}, not a LUT or a flip-flop')
        ins = arcs_into(iop, dc, dp)
        if len(ins) != 1 or luts_left == 0:
            raise NoVerdict(f'{dc}: {len(ins)} input arcs into {dp}, {luts_left} LUTs left in the budget')
        pin, (a, b) = ins[0]
        lo, hi, parts['lut'] = lo + a, hi + b, parts['lut'] + b
        parts['luts'].append(dc)
        cell, port, luts_left = dc, pin, luts_left - 1


def evaluate(ic, iop, ctype, obuf, ff_net_driver, ff_inverted, out=print):
    """obuf: {port: OBUF cell}; ff_net_driver: {net: FF cell}; ff_inverted: {FF cell: bool}.
    -> (verdict, rows); raises NoVerdict when the structure is not the pre-registered one."""
    tx_dly = S['TX_DLY']
    # TXC: one LUT, two input arcs, each straight to a flip-flop
    co = obuf[S['CLOCK_PORT']]
    dc, dp, (a_ic, b_ic) = ic.get((co, 'IN')) or (None, None, (0, 0))
    if ctype.get(dc) != 'SLICE_LUTX':
        raise NoVerdict(f"TXC buffer is driven by {dc} ({ctype.get(dc)}), not a LUT")
    ins = arcs_into(iop, dc, dp)
    if len(ins) != 2:
        raise NoVerdict(f'TXC LUT {dc}: {len(ins)} input arcs, want 2')
    branch = {}
    for pin, (a, b) in ins:
        w = walk_to_ff(ic, iop, ctype, dc, pin, 0)
        branch[w['ff']] = dict(w, lo=w['lo'] + a + a_ic, hi=w['hi'] + b + b_ic, pin=pin)
    fall_ff, rise_ff = ff_net_driver[S['FF_FALL_NET']], ff_net_driver[S['FF_RISE_NET']]
    if set(branch) != {fall_ff, rise_ff}:
        raise NoVerdict(f'TXC LUT inputs come from {sorted(branch)}, not from the {S["FF_FALL_NET"]} '
                        f'and {S["FF_RISE_NET"]} flip-flops')
    c_fall, c_rise = branch[fall_ff], branch[rise_ff]
    data = {}
    for p in S['DATA_PORTS']:
        w = walk_to_ff(ic, iop, ctype, obuf[p], 'IN', tx_dly)
        if len(w['luts']) != tx_dly:
            raise NoVerdict(f'{p}: {len(w["luts"])} LUTs between the flip-flop and the buffer, want {tx_dly}')
        data[p] = w
    srcs = {w['clk_src'] for w in list(data.values()) + [c_fall, c_rise]}
    if len(srcs) != 1:
        raise NoVerdict(f'the seven flip-flops have {len(srcs)} clock sources: {sorted(srcs)}')
    edges = {ff: ff_inverted.get(ff, False) for ff in [w['ff'] for w in data.values()] + [fall_ff, rise_ff]}
    if edges[rise_ff] is not True or any(v for ff, v in edges.items() if ff != rise_ff):
        raise NoVerdict(f'clock edges {edges}: want only the {S["FF_RISE_NET"]} flip-flop on the falling edge')

    out(f"clock: all seven flip-flops from {srcs.pop()[0]}; {S['FF_RISE_NET']} on the falling edge, the rest rising")
    for name, w in ((f"C_fall (via {S['FF_FALL_NET']}, pin {c_fall['pin']})", c_fall),
                    (f"C_rise (via {S['FF_RISE_NET']}, pin {c_rise['pin']})", c_rise)):
        out(f"TXC {name}: {w['hi']:.1f} ps  (clock {w['clk']:.1f}, clk-to-Q {w['c2q']:.1f}, "
            f"route {w['route'] + b_ic:.1f}, LUT {w['hi'] - w['clk'] - w['c2q'] - w['route'] - b_ic:.1f})")
    rows, bad = [], []
    for p, w in data.items():
        hold = w['lo'] - c_fall['hi']
        setup = S['RXC_HIGH_MIN_PS'] + c_rise['lo'] - w['hi']
        ok_h, ok_s = hold >= S['HOLD_MIN_PS'], setup >= S['SETUP_MIN_PS']
        rows.append(dict(port=p, d=w['hi'], hold=hold, setup=setup))
        bad += [] if ok_h and ok_s else [p]
        out(f"{p:11s} D {w['hi']:8.1f} ps over {len(w['luts'])} LUTs (clock {w['clk']:.1f}, clk-to-Q "
            f"{w['c2q']:.1f}, LUTs {w['lut']:.1f}, routes {w['route']:.1f}); hold_fall {hold:8.1f} "
            f"{'>=' if ok_h else '<'} {S['HOLD_MIN_PS']}; setup_rise {setup:8.1f} {'>=' if ok_s else '<'} "
            f"{S['SETUP_MIN_PS']}")
    return ('FAIL' if bad else 'PASS'), rows


def netlist_maps(routed):
    """From nextpnr's routed JSON: port -> OBUF cell, net -> driving FF cell, FF -> clock inverted."""
    top = next(iter(routed['modules'].values()))
    cells, nets = top['cells'], top['netnames']
    drv = {}
    for n, c in cells.items():
        for p, bits in c['connections'].items():
            if c['port_directions'].get(p) == 'output':
                for b in bits:
                    drv[b] = n
    obuf = {}
    for p in list(S['DATA_PORTS']) + [S['CLOCK_PORT']]:
        pad = cells.get(p)
        if not pad or pad['type'] != 'PAD':
            raise NoVerdict(f'no PAD cell {p} in the routed netlist')
        b = pad['connections']['PAD'][0]
        hit = [n for n, c in cells.items() if c['type'].endswith('OUTBUF') and c['connections'].get('OUT') == [b]]
        if len(hit) != 1:
            raise NoVerdict(f'{p}: {len(hit)} output buffers on the pad')
        obuf[p] = hit[0]
    ff_net = {}
    for n in (S['FF_FALL_NET'], S['FF_RISE_NET']):
        if n not in nets or nets[n]['bits'][0] not in drv:
            raise NoVerdict(f'net {n} has no driver in the routed netlist')
        ff_net[n] = drv[nets[n]['bits'][0]]
    inv = {n: int(str(c.get('parameters', {}).get('IS_CLK_INVERTED', '0')), 2) == 1
           for n, c in cells.items() if c['type'] == 'SLICE_FFX'}
    return obuf, ff_net, inv


# ---- the run -----------------------------------------------------------------------------------

def pinned():
    """Every file the spec pins, and the e3z build inputs. -> the paths nextpnr gets."""
    bad = []
    chk = [(os.path.join(REPO, SPEC_FILE), SPEC_SHA256), (os.path.join(REPO, S['RUNNER']), S['RUNNER_SHA256']),
           (expand(S['NEXTPNR_BIN']), S['NEXTPNR_SHA256']), (expand(S['CHIPDB']), S['CHIPDB_SHA256']),
           (os.path.join(S['BUILD_DIR'], 'node.json'), S['NODE_JSON_SHA256']),
           (os.path.join(S['BUILD_DIR'], 'node.fasm'), S['FASM_SHA256']),
           (os.path.join(S['BUILD_DIR'], 'src', os.path.basename(S['XDC_FILE'])), S['XDC_SHA256']),
           (os.path.join(REPO, S['XDC_FILE']), S['XDC_SHA256'])]
    for path, want in chk:
        got = sha256(path) if os.path.exists(path) else 'missing'
        print(f"  {'ok  ' if got == want else 'DIFF'} {path} {got[:16]}")
        bad += [] if got == want else [path]
    if bad:
        raise NoVerdict(f'pinned files differ: {bad}')


def run():
    t0 = time.time()
    stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    print(f"e3_tx_hold_model: {stamp} (UTC, time.gmtime); spec {SPEC_FILE} {SPEC_SHA256[:16]}")
    print('pinned files:')
    pinned()
    w = S['WORK_DIR']
    os.makedirs(w, exist_ok=True)
    sdf, fasm, routed = f'{w}/e3z.sdf', f'{w}/node.fasm', f'{w}/node_routed.json'
    for f in (sdf, fasm, routed):
        if os.path.exists(f):
            os.remove(f)
    cmd = [expand(S['NEXTPNR_BIN']), '--chipdb', expand(S['CHIPDB']),
           '--xdc', os.path.join(S['BUILD_DIR'], 'src', os.path.basename(S['XDC_FILE'])),
           '--json', os.path.join(S['BUILD_DIR'], 'node.json'), '--write', routed, '--fasm', fasm, '--sdf', sdf,
           '--freq', f"{S['FREQ_MHZ']}.0", '--seed', str(S['SEED']), '--placer', S['PLACER'],
           '--router', S['ROUTER'], '--timing-allow-fail']
    print('nextpnr: ' + ' '.join(cmd))
    with open(f'{w}/nextpnr.log', 'w') as lf:
        rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT).returncode
    print(f'nextpnr: exit {rc}, {time.time() - t0:.1f} s, log {w}/nextpnr.log')
    if rc != 0 or not all(os.path.exists(f) for f in (sdf, fasm, routed)):
        raise NoVerdict('nextpnr did not write the SDF, the FASM and the routed netlist')
    got = sha256(fasm)
    print(f"fasm: {got[:16]} {'= e3z' if got == S['FASM_SHA256'] else '!= e3z ' + S['FASM_SHA256'][:16]}")
    if got != S['FASM_SHA256']:
        raise NoVerdict('the FASM differs from e3z: another placement or routing')
    print(f'sdf: {sdf} {sha256(sdf)[:16]}, {os.path.getsize(sdf)} bytes')
    with open(sdf) as fh:
        ic, iop, ctype = read_sdf(fh.read())
    with open(routed) as fh:
        obuf, ff_net, inv = netlist_maps(json.load(fh))
    print(f'sdf: {len(ic)} interconnects, {len(iop)} cell arcs, {len(ctype)} cells')
    return evaluate(ic, iop, ctype, obuf, ff_net, inv)


def summary(verdict, rows):
    if rows:
        lo, hi = S['GUESS_HOLD_LO_PS'], S['GUESS_HOLD_HI_PS']
        inside = sum(lo <= r['hold'] <= hi for r in rows)
        m = min(rows, key=lambda r: r['hold'])
        print(f"guess (information only): hold_fall in [{lo}, {hi}] ps on {inside}/{len(rows)} pins")
        print(f"smallest hold_fall {m['hold']:.1f} ps on {m['port']}; the bench stands in "
              f"{S['BENCH_TX_DELAY_PS']} ps for the chain")
    print(f'VERDICT: {verdict}')


# ---- self-test ---------------------------------------------------------------------------------

def synthetic(tx_dly, lut_ps, route_ps, drop_arc=False):
    """A small SDF in nextpnr's layout: two data pins of tx_dly LUTs, the TXC LUT and its two FFs."""
    ics, cells = [], []

    def icl(fc, fp, tc, tp, d):
        e = lambda s: re.sub(r'([$\\\[\]:])', r'\\\1', s)
        ics.append(f'        (INTERCONNECT {e(fc + "/" + fp)} {e(tc + "/" + tp)} ({d}:{d}:{d}) ({d}:{d}:{d}))')

    def cell(t, name, arcs):
        body = ''.join(f'        (IOPATH {a} {b} ({d}:{d}:{d}) ({d}:{d}:{d}))\n' for a, b, d in arcs)
        esc = re.sub(r'([$\\\[\]:])', r'\\\1', name)
        cells.append(f'  (CELL\n    (CELLTYPE "{t}")\n    (INSTANCE {esc})\n    (DELAY\n      (ABSOLUTE\n'
                     f'{body}      )\n    )\n  )')

    cell('BUFGCTRL', 'u_bufg', [('I0', 'O', 200)])
    for i, port in enumerate(['p0', 'p1']):
        ff = f'$auto$ff.cc:1:slice${i}'
        cell('SLICE_FFX', ff, [('CK', 'Q', 300)])
        icl('u_bufg', 'O', ff, 'CK', 1000 + 10 * i)
        prev = (ff, 'Q')
        for s in range(tx_dly):
            lut = f'g[{i}].s[{s}].u_buf'
            cell('SLICE_LUTX', lut, [] if (drop_arc and i == 1 and s == 3) else [('A3', 'O6', lut_ps)])
            icl(*prev, lut, 'A3', route_ps)
            prev = (lut, 'O6')
        icl(*prev, f'ob_{port}', 'IN', route_ps)
        cell('IOB33_OUTBUF', f'ob_{port}', [])
    for n in ('fall', 'rise'):
        cell('SLICE_FFX', f'ff_{n}', [('CK', 'Q', 300)])
        icl('u_bufg', 'O', f'ff_{n}', 'CK', 1005)
    cell('SLICE_LUTX', 'u_txc', [('A5', 'O6', 100), ('A3', 'O6', 100)])
    icl('ff_fall', 'Q', 'u_txc', 'A5', 400)
    icl('ff_rise', 'Q', 'u_txc', 'A3', 500)
    icl('u_txc', 'O6', 'ob_c', 'IN', 600)
    cell('IOB33_OUTBUF', 'ob_c', [])
    return ('(DELAYFILE\n  (SDFVERSION "3.0")\n  (DESIGN "top")\n  (TIMESCALE 1ps)\n  (CELL\n    (CELLTYPE "top")\n'
            '    (INSTANCE )\n    (DELAY\n      (ABSOLUTE\n' + '\n'.join(ics) + '\n      )\n    )\n  )\n'
            + '\n'.join(cells) + '\n)\n')


def self_test():
    global S
    saved = S
    ok = True
    obuf = {'p0': 'ob_p0', 'p1': 'ob_p1', 'c': 'ob_c'}
    ff_net = {'n_fall': 'ff_fall', 'n_rise': 'ff_rise'}
    inv = {'ff_rise': True}
    S = dict(saved, DATA_PORTS=['p0', 'p1'], CLOCK_PORT='c', FF_FALL_NET='n_fall', FF_RISE_NET='n_rise', TX_DLY=4)
    quiet = lambda *_: None
    # C_fall = 1005 + 300 + 400 + 100 + 600 = 2405, C_rise = 1005 + 300 + 500 + 100 + 600 = 2505;
    # D_p0 = 1000 + 300 + 5 * 100 + 4 * lut_ps; hold = D_p0 - 2405, setup = 16000 + 2505 - D_p1
    cases = [('PASS: D 3800, hold 1395', dict(tx_dly=4, lut_ps=500, route_ps=100), 'PASS', 1395.0),
             ('FAIL on hold: D 2600, hold 195', dict(tx_dly=4, lut_ps=200, route_ps=100), 'FAIL', 195.0),
             ('FAIL on setup: D 19800, hold 17395', dict(tx_dly=4, lut_ps=4500, route_ps=100), 'FAIL', 17395.0),
             ('NO VERDICT: 3 LUTs, not 4', dict(tx_dly=3, lut_ps=500, route_ps=100), 'NO VERDICT', None),
             ('NO VERDICT: a LUT without its arc', dict(tx_dly=4, lut_ps=500, route_ps=100, drop_arc=True),
              'NO VERDICT', None)]
    try:
        for name, kw, want, hold in cases:
            try:
                ic, iop, ctype = read_sdf(synthetic(**kw))
                got, rows = evaluate(ic, iop, ctype, obuf, ff_net, inv, out=quiet)
                h = rows[0]['hold']
            except NoVerdict:
                got, h = 'NO VERDICT', None
            good = got == want and (hold is None or abs(h - hold) < 1e-6)
            ok &= good
            print(f"  {'ok  ' if good else 'FAIL'} {name}: got {got}" + (f', hold {h:.1f}' if h is not None else ''))
        ic, iop, ctype = read_sdf(synthetic(tx_dly=4, lut_ps=500, route_ps=100))
        esc = ('$auto$ff.cc:1:slice$0', 'CK') in ic
        ok &= esc
        print(f"  {'ok  ' if esc else 'FAIL'} escaped names read back ($ : [ ])")
        edge = dict(inv, ff_fall=True)
        try:
            evaluate(ic, iop, ctype, obuf, ff_net, edge, out=quiet)
            good = False
        except NoVerdict:
            good = True
        ok &= good
        print(f"  {'ok  ' if good else 'FAIL'} NO VERDICT: the fall flip-flop on the wrong edge")
    finally:
        S = saved
    print(f"self-test e3_tx_hold_model: {'PASS' if ok else 'FAIL'}")
    return ok


class Tee:
    def __init__(self, *fhs):
        self.fhs = fhs

    def write(self, s):
        for f in self.fhs:
            f.write(s)

    def flush(self):
        for f in self.fhs:
            f.flush()


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('--self-test', action='store_true')
    args = a.parse_args()
    if args.self_test:
        return 0 if self_test() else 1
    if os.path.exists(LOG):
        print(f'{LOG} exists: this check runs once; its record is that log', file=sys.stderr)
        return 2
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'w') as lf:
        out, sys.stdout = sys.stdout, Tee(sys.stdout, lf)
        try:
            try:
                verdict, rows = run()
            except NoVerdict as e:
                print(f'NO VERDICT: {e}')
                verdict, rows = 'NO VERDICT', []
            summary(verdict, rows)
        finally:
            sys.stdout = out
    return {'PASS': 0, 'FAIL': 1}.get(verdict, 2)


if __name__ == '__main__':
    sys.exit(main())
