#!/usr/bin/env python3
"""E3 receive capture timing in nextpnr-xilinx's own delay model, for the routed e3z netlist.

Pre-registered in specs/trinet/e3_rx_capture_model_ax7203.t27 (constants from e3_rx_capture_params.py,
which e3_rx_capture_from_spec.mjs writes from it). The spec has the check, the PHY-side ranges, the
prediction and what the result does not say; this file only carries it out.

No tool runs. The SDF, the routed netlist and the FASM are the ones the TX model's one run wrote
(conformance/e3_tx_hold_model.py; its log has the FASM equal to e3z's) and are accepted by sha256
only. The SDF reader is imported from that runner, whose sha256 is pinned too. For each RX flip-flop
the clock path runs from the RXC input buffer through the BUFG to the clock pin, the data path from
the data pad's input buffer straight to the D pin; their difference against the flip-flop's own
setup and hold, and the PHY-side ranges of the spec, give the margins and the information lines.

    python3 conformance/e3_rx_capture_model.py              # the run; exit 0 PASS, 1 FAIL, 2 NO VERDICT
    python3 conformance/e3_rx_capture_model.py --self-test  # the checks on synthetic netlists; no files
"""
import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from e3_rx_capture_params import SPEC as S, SPEC_FILE, SPEC_SHA256  # noqa: E402
from e3_tx_hold_model import NoVerdict, Tee, delay, parse_sexpr, read_sdf, sha256  # noqa: E402

LOG = os.path.join(HERE, 'model_runs', 'e3_rx_capture_model.log')


def read_checks(text):
    """-> {(cell, pin): [(setup, hold, clock edge), ...]} from the SETUPHOLD timing checks; the
    largest of min:typ:max each."""
    root = parse_sexpr(text)
    out = {}
    for cell in (x for x in root[1:] if isinstance(x, list) and x and x[0] == 'CELL'):
        f = {x[0]: x[1:] for x in cell[1:]}
        inst = f['INSTANCE'][0] if f['INSTANCE'] else ''
        for chk in f.get('TIMINGCHECK', []):
            if chk[0] != 'SETUPHOLD':
                continue
            (_, dpin), (cedge, cpin) = chk[1], chk[2]
            out.setdefault((inst, dpin), []).append((delay([chk[3]])[1], delay([chk[4]])[1], f'{cedge} {cpin}'))
    return out


def netlist_maps(routed):
    """From nextpnr's routed JSON: port -> input buffer cell, net -> driving FF cell, the BUFG that
    drives RXC_NET, FF -> clock inverted."""
    top = next(iter(routed['modules'].values()))
    cells, nets = top['cells'], top['netnames']
    drv = {}
    for n, c in cells.items():
        for p, bits in c['connections'].items():
            if c['port_directions'].get(p) == 'output':
                for b in bits:
                    drv[b] = n
    ibuf = {}
    for p in list(S['DATA_PORTS']) + [S['CTL_PORT'], S['CLOCK_PORT']]:
        pad = cells.get(p)
        if not pad or pad['type'] != 'PAD':
            raise NoVerdict(f'no PAD cell {p} in the routed netlist')
        b = pad['connections']['PAD'][0]
        hit = [n for n, c in cells.items() if c['type'].endswith('INBUF_EN') and c['connections'].get('PAD') == [b]]
        if len(hit) != 1:
            raise NoVerdict(f'{p}: {len(hit)} input buffers on the pad')
        ibuf[p] = hit[0]
    names = [f"{S[k]}[{i}]" for k in ('MID_NET', 'START_NET') for i in range(len(S['DATA_PORTS']))]
    ff = {}
    for n in names + [S['CTL_MID_NET'], S['RXC_NET']]:
        if n not in nets or len(nets[n]['bits']) != 1 or nets[n]['bits'][0] not in drv:
            raise NoVerdict(f'net {n} has no single driver in the routed netlist')
        ff[n] = drv[nets[n]['bits'][0]]
    bufg = ff.pop(S['RXC_NET'])
    inv = {n: int(str(c.get('parameters', {}).get('IS_CLK_INVERTED', '0')), 2) == 1
           for n, c in cells.items() if c['type'] == 'SLICE_FFX'}
    return ibuf, ff, bufg, inv


def classify(dsu, dho, x):
    """A sample taken at a change x ps from its clock edge: 'new', 'old' or 'undetermined'."""
    lo, hi = x if isinstance(x, tuple) else (x, x)
    if hi <= dsu:
        return 'new'
    if lo >= dho:
        return 'old'
    return 'undetermined'


def evaluate(ic, iop, ctype, checks, ibuf, ff, bufg, inv, out=print):
    """-> (verdict, rows, info); raises NoVerdict when the structure is not the pre-registered one."""
    ndata = len(S['DATA_PORTS'])
    if ctype.get(bufg) != 'BUFGCTRL':
        raise NoVerdict(f"{S['RXC_NET']} is driven by {bufg} ({ctype.get(bufg)}), not a BUFGCTRL")
    src = ic.get((bufg, 'I0'))
    if not src or src[:2] != (ibuf[S['CLOCK_PORT']], 'OUT'):
        raise NoVerdict(f"{bufg}.I0 is driven by {src[:2] if src else None}, not {S['CLOCK_PORT']}'s input buffer")
    if (bufg, 'I0', 'O') not in iop:
        raise NoVerdict(f'no IOPATH I0 -> O in {bufg}')
    c_in, c_buf = src[2], iop[(bufg, 'I0', 'O')]
    plan = ([(f"{S['MID_NET']}[{i}]", S['DATA_PORTS'][i], True) for i in range(ndata)]
            + [(f"{S['START_NET']}[{i}]", S['DATA_PORTS'][i], False) for i in range(ndata)]
            + [(S['CTL_MID_NET'], S['CTL_PORT'], True)])
    rows = {}
    for net, port, want_inv in plan:
        cell = ff[net]
        if ctype.get(cell) != 'SLICE_FFX':
            raise NoVerdict(f'{net} is driven by {cell} ({ctype.get(cell)}), not a flip-flop')
        d = ic.get((cell, 'D'))
        if not d or d[:2] != (ibuf[port], 'OUT'):
            raise NoVerdict(f"{net}: D is driven by {d[:2] if d else None}, not straight from {port}'s input buffer")
        ck = ic.get((cell, 'CK'))
        if not ck or ck[:2] != (bufg, 'O'):
            raise NoVerdict(f'{net}: CK is driven by {ck[:2] if ck else None}, not {bufg}.O')
        if inv.get(cell, False) != want_inv:
            raise NoVerdict(f"{net}: clock {'inverted' if inv.get(cell) else 'not inverted'}, want the "
                            f"{'falling' if want_inv else 'rising'} edge")
        sh = checks.get((cell, 'D'))
        if not sh:
            raise NoVerdict(f'{net}: no SETUPHOLD on D in {cell}')
        tsu, th = max(s for s, _, _ in sh), max(h for _, h, _ in sh)
        c_lo, c_hi = c_in[0] + c_buf[0] + ck[2][0], c_in[1] + c_buf[1] + ck[2][1]
        d_lo, d_hi = d[2]
        rows[net] = dict(net=net, cell=cell, c=c_hi, clk_route=ck[2][1], d=d_hi, tsu=tsu, th=th,
                         dsu=c_lo - d_hi - tsu, dho=c_hi - d_lo + th, delta=c_hi - d_hi, n_checks=len(sh))

    early, late, nom = S['X_EARLY_MAX_PS'], S['X_LATE_MAX_PS'], S['PHY_DELAY_NOM_PS']
    out(f"clock: all {len(rows)} flip-flops from {bufg}; RXC input buffer -> I0 {c_in[1]:.1f} ps, "
        f"BUFG I0 -> O {c_buf[1]:.1f} ps; {S['MID_NET']} and {S['CTL_MID_NET']} on the falling edge, "
        f"{S['START_NET']} rising")
    out(f"x (data change from its RXC edge at the pads): -{early} .. +{late} ps, nominal -{nom}")
    bad = []
    for net, _, _ in plan[:ndata] + plan[-1:]:
        r = rows[net]
        r['setup'] = S['RXC_HIGH_MIN_PS'] + (r['dsu']) - late
        r['hold'] = S['RXC_LOW_MIN_PS'] - early - r['dho']
        ok_s, ok_h = r['setup'] >= S['MARGIN_MIN_PS'], r['hold'] >= S['MARGIN_MIN_PS']
        bad += [] if ok_s and ok_h else [net]
        out(f"{net:10s} mid-nibble: C {r['c']:8.1f}  D {r['d']:8.1f}  Delta {r['delta']:8.1f}  Tsu {r['tsu']:6.1f} "
            f"Th {r['th']:6.1f} ps; setup {r['setup']:8.1f} {'>=' if ok_s else '<'} {S['MARGIN_MIN_PS']}; "
            f"hold {r['hold']:8.1f} {'>=' if ok_h else '<'} {S['MARGIN_MIN_PS']}")
    info = {}
    for net, _, _ in plan[ndata:]:
        r = rows[net]
        r['range'] = classify(r['dsu'], r['dho'], (-early, late))
        r['nominal'] = classify(r['dsu'], r['dho'], -nom)
        out(f"{net:10s} at the rising edge: C {r['c']:8.1f}  D {r['d']:8.1f}  Delta {r['delta']:8.1f} ps; new for "
            f"x <= {r['dsu']:.1f}, old for x >= {r['dho']:.1f}; over the range {r['range']}, at nominal "
            f"{r['nominal']}")
    ctl = rows[S['CTL_MID_NET']]
    info['rxer_range'] = classify(ctl['dsu'], ctl['dho'], (-early, late))
    info['rxer_nominal'] = classify(ctl['dsu'], ctl['dho'], -nom)
    out(f"{S['CTL_MID_NET']:10s} at an RX_ER nibble's falling-edge change: new for x <= {ctl['dsu']:.1f}, old for "
        f"x >= {ctl['dho']:.1f}; over the range {info['rxer_range']}, at nominal {info['rxer_nominal']}")
    for k in ('range', 'nominal'):
        got = [rows[n][k] for n, _, _ in plan[ndata:2 * ndata]]
        info[f'ed_{k}'] = 'new' if all(g == 'new' for g in got) else 'old' if 'old' in got else 'undetermined'
    return ('FAIL' if bad else 'PASS'), rows, info


# ---- the run -----------------------------------------------------------------------------------

def load():
    a, b, c = os.getloadavg()
    return f'load average {a:.2f} {b:.2f} {c:.2f} on {os.cpu_count()} cpus'


def pinned():
    bad = []
    chk = [(os.path.join(REPO, SPEC_FILE), SPEC_SHA256), (os.path.join(REPO, S['RUNNER']), S['RUNNER_SHA256']),
           (os.path.join(REPO, S['TX_RUNNER_FILE']), S['TX_RUNNER_SHA256']),
           (S['SDF_FILE'], S['SDF_SHA256']), (S['ROUTED_FILE'], S['ROUTED_SHA256']), (S['FASM_FILE'], S['FASM_SHA256'])]
    for path, want in chk:
        got = sha256(path) if os.path.exists(path) else 'missing'
        print(f"  {'ok  ' if got == want else 'DIFF'} {path} {got[:16]}")
        bad += [] if got == want else [path]
    if os.path.exists(S['SDF_FILE']) and os.path.getsize(S['SDF_FILE']) != S['SDF_BYTES']:
        bad.append(f"{S['SDF_FILE']} size")
    if bad:
        raise NoVerdict(f'pinned files differ: {bad}')


def run():
    t0 = time.time()
    stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    print(f"e3_rx_capture_model: {stamp} (UTC, time.gmtime); spec {SPEC_FILE} {SPEC_SHA256[:16]}")
    print(f'start: {load()}')
    print('pinned files:')
    pinned()
    with open(S['SDF_FILE']) as fh:
        text = fh.read()
    ic, iop, ctype = read_sdf(text)
    t1 = time.time()
    checks = read_checks(text)
    t2 = time.time()
    with open(S['ROUTED_FILE']) as fh:
        maps = netlist_maps(json.load(fh))
    t3 = time.time()
    print(f'sdf: {len(ic)} interconnects, {len(iop)} cell arcs, {len(ctype)} cells, {len(checks)} checked pins; '
          f'read {t1 - t0:.1f} s, checks {t2 - t1:.1f} s, netlist {t3 - t2:.1f} s')
    return evaluate(ic, iop, ctype, checks, *maps)


def summary(verdict, rows, info):
    if info:
        print(f"guess (information only): verdict {S['GUESS_VERDICT']}; ed over the range {S['GUESS_ED_RANGE']}, at "
              f"nominal {S['GUESS_ED_NOMINAL']}; RX_ER over the range {S['GUESS_RXER_RANGE']}, at nominal "
              f"{S['GUESS_RXER_NOMINAL']}")
        print(f"model (information only): ed over the range {info['ed_range']}, at nominal {info['ed_nominal']}; "
              f"RX_ER over the range {info['rxer_range']}, at nominal {info['rxer_nominal']}")
        mids = [r for r in rows.values() if 'setup' in r]
        m = min(mids, key=lambda r: min(r['setup'], r['hold']))
        print(f"smallest mid-nibble margin {min(m['setup'], m['hold']):.1f} ps on {m['net']}")
    print(f'end: {load()}')
    print(f'VERDICT: {verdict}')


# ---- self-test ---------------------------------------------------------------------------------

def synthetic(ck_ps, d_ps, lut_on=None, second_bufg=None, no_check=None):
    """A small SDF in nextpnr's layout: RXC buffer -> BUFG -> five flip-flops, two data pads and RX_CTL."""
    ics, cells = [], []
    e = lambda s: re.sub(r'([$\\\[\]:])', r'\\\1', s)

    def icl(fc, fp, tc, tp, d):
        ics.append(f'        (INTERCONNECT {e(fc + "/" + fp)} {e(tc + "/" + tp)} ({d}:{d}:{d}) ({d}:{d}:{d}))')

    def cell(t, name, arcs, checks=()):
        body = ''.join(f'        (IOPATH {a} {b} ({d}:{d}:{d}) ({d}:{d}:{d}))\n' for a, b, d in arcs)
        tc = ''.join(f'      (SETUPHOLD ({g} {p}) (posedge CK) ({s}:{s}:{s}) ({h}:{h}:{h}))\n' for g, p, s, h in checks)
        cells.append(f'  (CELL\n    (CELLTYPE "{t}")\n    (INSTANCE {e(name)})\n    (DELAY\n      (ABSOLUTE\n{body}'
                     f'      )\n    )\n' + (f'    (TIMINGCHECK\n{tc}    )\n' if tc else '') + '  )')

    for b in ('ib_k', 'ib_d0', 'ib_d1', 'ib_c'):
        cell('IOB33_INBUF_EN', b, [])
    cell('BUFGCTRL', 'bg', [('I0', 'O', 200)])
    icl('ib_k', 'OUT', 'bg', 'I0', 100)
    if second_bufg:
        cell('BUFGCTRL', 'bg2', [('I0', 'O', 200)])
        icl('ib_k', 'OUT', 'bg2', 'I0', 100)
    for ffn, ib in (('$auto$ff.cc:1:slice$0', 'ib_d0'), ('ff_m1', 'ib_d1'), ('ff_s0', 'ib_d0'), ('ff_s1', 'ib_d1'),
                    ('ff_cm', 'ib_c')):
        chk = [] if ffn == no_check else [('posedge', 'D', 50, 40), ('negedge', 'D', 45, 60), ('posedge', 'CE', 900, 900)]
        cell('SLICE_FFX', ffn, [('CK', 'Q', 300)], chk)
        icl('bg2' if ffn == second_bufg else 'bg', 'O', ffn, 'CK', ck_ps)
        if ffn == lut_on:
            cell('SLICE_LUTX', 'lut', [('A1', 'O6', 100)])
            icl(ib, 'OUT', 'lut', 'A1', d_ps)
            icl('lut', 'O6', ffn, 'D', 0)
        else:
            icl(ib, 'OUT', ffn, 'D', d_ps)
    return ('(DELAYFILE\n  (SDFVERSION "3.0")\n  (DESIGN "top")\n  (TIMESCALE 1ps)\n  (CELL\n    (CELLTYPE "top")\n'
            '    (INSTANCE )\n    (DELAY\n      (ABSOLUTE\n' + '\n'.join(ics) + '\n      )\n    )\n  )\n'
            + '\n'.join(cells) + '\n)\n')


def synthetic_routed(two_ibufs=False):
    cells, nets, bit = {}, {}, [100]

    def new():
        bit[0] += 1
        return bit[0]

    def c(name, t, conns, dirs, params=None):
        cells[name] = dict(type=t, connections=conns, port_directions=dirs, parameters=params or {})

    for port, ib in (('d[0]', 'ib_d0'), ('d[1]', 'ib_d1'), ('c', 'ib_c'), ('k', 'ib_k')):
        b = new()
        c(port, 'PAD', {'PAD': [b]}, {'PAD': 'output'})
        c(ib, 'IOB33_INBUF_EN', {'PAD': [b], 'OUT': [new()]}, {'PAD': 'input', 'OUT': 'output'})
        if two_ibufs and port == 'd[1]':
            c('ib_extra', 'IOB33_INBUF_EN', {'PAD': [b], 'OUT': [new()]}, {'PAD': 'input', 'OUT': 'output'})
    for net, ffn, inv in (('m[0]', '$auto$ff.cc:1:slice$0', 1), ('m[1]', 'ff_m1', 1), ('s[0]', 'ff_s0', 0),
                          ('s[1]', 'ff_s1', 0), ('cm', 'ff_cm', 1)):
        q = new()
        c(ffn, 'SLICE_FFX', {'Q': [q]}, {'Q': 'output'}, {'IS_CLK_INVERTED': '1' if inv else '0'})
        nets[net] = dict(bits=[q])
    q = new()
    c('bg', 'BUFGCTRL', {'O': [q]}, {'O': 'output'})
    nets['rxc'] = dict(bits=[q])
    return {'modules': {'top': {'cells': cells, 'netnames': nets}}}


def self_test():
    global S
    saved = S
    ok = True
    S = dict(saved, DATA_PORTS=['d[0]', 'd[1]'], CTL_PORT='c', CLOCK_PORT='k', MID_NET='m', START_NET='s',
             CTL_MID_NET='cm', RXC_NET='rxc')
    quiet = lambda *_: None
    try:
        ibuf, ff, bufg, inv = netlist_maps(synthetic_routed())
        good = (ibuf == {'d[0]': 'ib_d0', 'd[1]': 'ib_d1', 'c': 'ib_c', 'k': 'ib_k'} and bufg == 'bg'
                and ff['m[0]'] == '$auto$ff.cc:1:slice$0' and inv['ff_cm'] and not inv['ff_s1'])
        ok &= good
        print(f"  {'ok  ' if good else 'FAIL'} routed netlist: pads, buffers, flip-flops, BUFG, clock edges")
        try:
            netlist_maps(synthetic_routed(two_ibufs=True))
            good = False
        except NoVerdict:
            good = True
        ok &= good
        print(f"  {'ok  ' if good else 'FAIL'} NO VERDICT: two input buffers on one pad")
        # C = 100 + 200 + ck; Tsu 50, Th 60 (the larger of the two D checks; CE ignored).
        # setup = 16000 + (C - D - 50) - 500, hold = 16000 - 2500 - (C - D + 60)
        cases = [('PASS; ed undetermined, new at nominal: Delta 500', dict(ck_ps=1000, d_ps=800),
                  'PASS', 15950.0, 12940.0, ('undetermined', 'new')),
                 ('PASS; ed new over the range: Delta 1300', dict(ck_ps=1500, d_ps=500),
                  'PASS', 16750.0, 12140.0, ('new', 'new')),
                 ('PASS; ed old over the range: Delta -2700', dict(ck_ps=0, d_ps=3000),
                  'PASS', 12750.0, 16140.0, ('old', 'old')),
                 ('FAIL on hold: Delta 13000', dict(ck_ps=13000, d_ps=300), 'FAIL', 28450.0, 440.0, None),
                 ('FAIL on setup: Delta -14700', dict(ck_ps=0, d_ps=15000), 'FAIL', 750.0, 28140.0, None),
                 ('NO VERDICT: a LUT between the buffer and a flip-flop', dict(ck_ps=1000, d_ps=800, lut_on='ff_m1'),
                  'NO VERDICT', None, None, None),
                 ('NO VERDICT: one flip-flop on a second BUFG', dict(ck_ps=1000, d_ps=800, second_bufg='ff_s0'),
                  'NO VERDICT', None, None, None),
                 ('NO VERDICT: a flip-flop without SETUPHOLD', dict(ck_ps=1000, d_ps=800, no_check='ff_cm'),
                  'NO VERDICT', None, None, None)]
        for name, kw, want, setup, hold, ed in cases:
            try:
                text = synthetic(**kw)
                ic, iop, ctype = read_sdf(text)
                got, rows, info = evaluate(ic, iop, ctype, read_checks(text), ibuf, ff, bufg, inv, out=quiet)
                r = rows['m[0]']
                s_h, ed_got = (r['setup'], r['hold']), (info['ed_range'], info['ed_nominal'])
            except NoVerdict:
                got, s_h, ed_got = 'NO VERDICT', None, None
            good = got == want and (setup is None or (abs(s_h[0] - setup) < 1e-6 and abs(s_h[1] - hold) < 1e-6))
            good &= ed is None or ed_got == ed
            ok &= good
            print(f"  {'ok  ' if good else 'FAIL'} {name}: got {got}"
                  + (f', setup {s_h[0]:.1f} hold {s_h[1]:.1f}, ed {ed_got}' if s_h else ''))
        text = synthetic(ck_ps=1000, d_ps=800)
        ic, iop, ctype = read_sdf(text)
        esc = ('$auto$ff.cc:1:slice$0', 'D') in read_checks(text)
        ok &= esc
        print(f"  {'ok  ' if esc else 'FAIL'} escaped names read back in the timing checks ($ :)")
        try:
            evaluate(ic, iop, ctype, read_checks(text), ibuf, ff, bufg, dict(inv, ff_s0=True), out=quiet)
            good = False
        except NoVerdict:
            good = True
        ok &= good
        print(f"  {'ok  ' if good else 'FAIL'} NO VERDICT: a rising-edge flip-flop on the falling edge")
        good = (classify(100, 200, -50) == 'new' and classify(100, 200, 150) == 'undetermined'
                and classify(100, 200, 200) == 'old' and classify(100, 200, (-50, 150)) == 'undetermined')
        ok &= good
        print(f"  {'ok  ' if good else 'FAIL'} classify: new at or below Delta - Tsu, old at or above Delta + Th")
    finally:
        S = saved
    print(f"self-test e3_rx_capture_model: {'PASS' if ok else 'FAIL'}")
    return ok


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
                verdict, rows, info = run()
            except NoVerdict as e:
                print(f'NO VERDICT: {e}')
                verdict, rows, info = 'NO VERDICT', {}, {}
            summary(verdict, rows, info)
        finally:
            sys.stdout = out
    return {'PASS': 0, 'FAIL': 1}.get(verdict, 2)


if __name__ == '__main__':
    sys.exit(main())
