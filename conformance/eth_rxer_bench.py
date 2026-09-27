#!/usr/bin/env python3
"""RX_ER cases for the E3 design, in simulation, beside the pinned bench.

enjoy-digital/liteeth#232 reports RGMII receivers that drop the falling-edge RX_CTL sample, so
RX_ER never reaches the MAC. E3 keeps only that sample (RX_DV xor RX_ER, RTL line 166). This
bench checks what E3 does with it. The KSZ9031 frame model has no RX_ER, so
formal/eth_rxer_inject.v forces RX_CTL for one falling edge as a second top module. The pinned
testbench, model, RTL and runner are compiled unchanged; frames, references and parsers come from
the runner by import.

The expectations below were written from reading the RTL before the first run (NODE_ETHERNET_PLAN.md,
RX_ER bench, has the stamp). A case that disagrees is a finding about the RTL or about that
reading. It is not a reason to change the expectation.

    python3 conformance/eth_rxer_bench.py            # all cases, exit 1 if any disagrees
    python3 conformance/eth_rxer_bench.py --gate     # the same on RTL and on yosys's netlist, and
                                                     # each gate log equal to its RTL log
"""
import argparse
import concurrent.futures
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eth_arp_icmp_ax7203 as r  # noqa: E402

INJ = 'formal/eth_rxer_inject.v'
WORK = '/tmp/e3rxer'
PRE_NIB = 16                        # preamble + SFD nibbles before frame byte 0


def raw_frame():
    """A frame for our MAC with a local ethertype. Its payload holds 55 D5 at frame byte 34, so an
    error on the nibble just before it leaves a tail that starts 5 5 5 D, a false SFD."""
    body = r.MAC + r.HOST_MAC + b'\x88\xb5' + bytes(20) + b'\x55\xd5' + bytes(80)
    return body + r.fcs(body)


PING = r.echo_request(56, seq=40)
ARP = r.arp_request()
BASE = dict(rx=2, fe=0, ce=0, aq=1, ar=1, eq=1, er=1)

# name, what, frames, plusargs, answered request indexes, counters, INJ edges.
CASES = [
    ('control', 'ping then ARP, no injection: the injector must not disturb the bench',
     [PING, ARP], dict(RXER_MODE=0), [0, 1], BASE, 0),
    ('er_in_ip_header', 'RX_ER on data nibble 60 of the ping (IP destination, first byte): the frame '
     'ends there, 30 bytes, below 64: fe; the tail starts with nibble C and is skipped',
     [PING, ARP], dict(RXER_MODE=1, RXER_FRAME=1, RXER_NIBBLE=PRE_NIB + 60), [1],
     dict(BASE, fe=1, eq=0, er=0), 1),
    ('er_in_preamble', 'RX_ER on preamble nibble 5 of the ping: R_PRE clears r_5, the next 5s set it '
     'again, the SFD starts the frame: answered as if no error (802.3 22.2.2.5 would drop it)',
     [PING, ARP], dict(RXER_MODE=1, RXER_FRAME=1, RXER_NIBBLE=5), [0, 1], BASE, 1),
    ('er_then_false_sfd', 'RX_ER on data nibble 67 of a frame whose payload has 55 D5 next: the '
     'frame ends (34 bytes: fe), the tail 5 5 5 D starts a second frame (84 bytes, FCS of the whole: '
     'fe). One errored frame counts rx 2, fe 2. Then the ARP is answered',
     [raw_frame(), ARP], dict(RXER_MODE=1, RXER_FRAME=1, RXER_NIBBLE=PRE_NIB + 67), [1],
     dict(rx=3, fe=2, ce=0, aq=1, ar=1, eq=0, er=0), 1),
    ('false_carrier', 'four nibbles of false carrier (DV 0, ER 1, RXD E) 40 nibbles after the ping: '
     'R_PRE sees E, goes to R_SKIP until the falling sample drops: no counter, both answered',
     [PING, ARP], dict(RXER_MODE=2, RXER_FRAME=1, RXER_NIBBLE=40, RXER_COUNT=4), [0, 1], BASE, 4),
]

INJ_EDGE = re.compile(r'^INJ t=(\d+) rxctl=(\d) rtl_falling_sample=(\d)$', re.M)
COMPARED = ('INJ', 'RXE', 'TXF', 'TB', 'UART|')   # the lines a gate log must share with its RTL log


def run_case(name, frames, plus, design=None):
    """design None: the pinned RTL; else the gate netlist, compiled as the runner's own gate run."""
    os.makedirs(WORK, exist_ok=True)
    tag = f'gate_{name}' if design else name
    stim, exe = f'{WORK}/{name}.hex', f'{WORK}/{tag}.vvp'
    with open(stim, 'w') as fh:
        fh.write('\n'.join(r.stim_words([r.F(f) for f in frames])) + '\n')
    cmd = ['iverilog', '-g2012', '-o', exe, '-s', r.TBTOP, '-s', 'eth_rxer_inject']
    if design:
        cmd += ['-DGATE', r.TB, r.MODEL, design, r.MOCK, f'{WORK}/cells_sim_no_ramb36e1.v', r.RAMB_MOCK, INJ]
    else:
        cmd += [r.TB, r.MODEL, r.RTL, r.MOCK, r.CELLS, INJ]
    p = subprocess.run(cmd, cwd=r.REPO, capture_output=True, text=True)
    if p.returncode != 0:
        return None, 'iverilog failed:\n' + p.stderr[-2000:]
    args = ['vvp', '-n', exe, f'+STIM={stim}'] + [f'+{k}={v}' for k, v in plus.items()]
    p = subprocess.run(args, cwd=r.REPO, capture_output=True, text=True)
    with open(f'{WORK}/{tag}.txt', 'w') as fh:
        fh.write(p.stdout)
    return p.stdout, None


def compared_lines(out):
    return [l for l in out.splitlines() if l.startswith(COMPARED)]


def check(frames, answered, cnt, edges, out):
    bad = []
    tb = r.TBSUM.search(out)
    if not tb:
        return [f'no TB summary line ({"timeout" if "TB TIMEOUT" in out else "crash"})'], ''
    errs, _, mx, ntx, frm, _ = map(int, tb.groups())
    for k, v in (('model_errors', errs), ('mdio_x', mx), ('uart_framing', frm)):
        if v:
            bad.append(f'{k}={v}')
    inj = INJ_EDGE.findall(out)
    if len(inj) != edges:
        bad.append(f'{len(inj)} injected edges, want {edges}')
    for t, v, s in inj:
        if v != s:
            bad.append(f'INJ t={t}: forced {v}, the RTL sampled {s}')
    want = [r.reference(frames[i])[1] for i in answered]
    got = r.tx_frames(out)
    if ntx != len(got) or len(got) != len(want):
        bad.append(f'{len(got)} TXF lines (model {ntx}), want {len(want)} replies')
    for i, ((_, _, data, prob), w) in enumerate(zip(got, want)):
        bad += [f'TX {i}: {p}' for p in prob]
        if data != w:
            bad.append(f'TX {i}: reply differs from the reference')
    reps = [r.parse(l[5:]) for l in out.splitlines() if l.startswith('UART|')]
    if not reps or reps[-1] is None:
        return bad + ['no parsable UART line'], tb.group(0)
    got_c = {k: reps[-1][k] for k in r.COUNTERS}
    if got_c != cnt:
        bad.append(f'counters {got_c}, want {cnt}')
    if reps[-1]['lk'] != 1:
        bad.append('lk=0')
    return bad, f"{tb.group(0)} | {' '.join(f'{k}={v}' for k, v in got_c.items())}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--gate', action='store_true', help='also run every case on the yosys netlist')
    ap.add_argument('--jobs', type=int, default=5)
    a = ap.parse_args()
    os.chdir(r.REPO)
    os.makedirs(WORK, exist_ok=True)
    design = None
    if a.gate:
        r.WORK = WORK                  # the runner's netlist helpers write under its WORK
        design = r.gate_netlist()
        r.cells_without_ramb36()
    fails = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = {(c[0], d): ex.submit(run_case, c[0], c[2], c[3], d)
                for c in CASES for d in ([None, design] if design else [None])}
        for name, what, frames, plus, answered, cnt, edges in CASES:
            print(f'{name}: {what}')
            outs = {}
            for d in ([None, design] if design else [None]):
                out, err = futs[(name, d)].result()
                bad, summ = ([err], '') if err else check(frames, answered, cnt, edges, out)
                outs[d] = out
                fails += bool(bad)
                print(f"  {'PASS' if not bad else 'FAIL'} {'gate' if d else 'rtl '}  {summ}")
                for b in bad:
                    print(f'     - {b}')
            if design and not (outs[None] and outs[design]):
                fails += 1
                print('  FAIL gate log = rtl log: a run has no output to compare')
            elif design:
                a_l, b_l = compared_lines(outs[None]), compared_lines(outs[design])
                diff = [(x, y) for x, y in zip(a_l, b_l) if x != y]
                same = not diff and len(a_l) == len(b_l)
                fails += not same
                print(f"  {'PASS' if same else 'FAIL'} gate log = rtl log: {len(a_l)} and {len(b_l)} compared lines"
                      + ('' if same else f", first difference: {diff[0] if diff else 'length'}"))
    n = len(CASES) * (3 if design else 1)
    print(f'{n - fails}/{n} checks as pre-registered; logs in {WORK}/')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
