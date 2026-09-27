#!/usr/bin/env python3
"""Ethernet step E2: check fpga/vivado/eth_phy_status_ax7203.v, and read its report line.

    python3 conformance/eth_phy_status_ax7203.py --static   full-size parameters against the KSZ9031
    python3 conformance/eth_phy_status_ax7203.py --sim      RTL against formal/ksz9031_status_model.v
    python3 conformance/eth_phy_status_ax7203.py --gate     the same on yosys's netlist
    python3 conformance/eth_phy_status_ax7203.py --parse F  decode report lines saved in a file
    python3 conformance/eth_phy_status_ax7203.py --port P   read the board  (NOT RUN: E2 is not flashed)

--sim and --gate each run two scenarios: a PHY that links at 100FD after auto-negotiation, and one
that never links (the design must reset it every NOLINK_POLLS polls and count it in rt). The gate
run synthesises with the build's own synth_xilinx flags and bakes the testbench's scaled
parameters in with chparam, so the netlist that is simulated is the one the build would make at
those sizes; the full sizes are checked by --static instead, at both ends of the measured CFGMCLK
range. conformance/NODE_ETHERNET_PLAN.md, step E2, has the results.
"""
import argparse
import os
import re
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RTL = 'fpga/vivado/eth_phy_status_ax7203.v'
TB = 'formal/eth_phy_status_tb.v'
MODEL = 'formal/ksz9031_status_model.v'
MOCK = 'fpga/openxc7-synth/STARTUPE2_mock.v'
CELLS = '/opt/homebrew/share/yosys/xilinx/cells_sim.v'
SYNTH = 'synth_xilinx -flatten -abc9 -nocarry -nodsp -nosrl -arch xc7 -top eth_phy_status_ax7203'
WORK = '/tmp/e2sim'

# Full-size parameters (the RTL defaults) and the testbench's scaled ones.
FULL = dict(RST_LOG2=20, WAIT_LOG2=21, POLL_LOG2=25, WIN_LOG2=20, MDC_LOG2=5, BAUD_DIV=60, NOLINK_POLLS=30)
SCALED = dict(RST_LOG2=6, WAIT_LOG2=7, POLL_LOG2=17, WIN_LOG2=12, NOLINK_POLLS=4)
TB_MCLK_NS = 14                       # STARTUPE2 mock period
CFGMCLK_HZ = (65.6e6, 68.7e6)         # measured range over the board chips (cp2102n-rate-grid)

# KSZ9031RNX datasheet limits the design must meet on every chip in CFGMCLK_HZ.
RESET_MIN_S = 10e-3                   # reset pulse, once supplies are stable
MDIO_WAIT_MIN_S = 100e-6              # reset release to the first MDIO access
MDC_MAX_HZ = 2.5e6

PHYID = 0x00221622
MODEL_ADDR = 1
FIELD = r'([0-9A-F]{%d})'
LINE = re.compile(
    r'E2 n=%s rt=%s pm=%s id=%s g9=%s>%s a4=%s>%s cr=%s sr=%s/%s pc=%s ib=%s%s rc=%s fr=%s$'
    % tuple(FIELD % w for w in (4, 2, 8, 8, 4, 4, 4, 4, 4, 4, 4, 4, 1, 1, 6, 4)))
NAMES = ('n', 'rt', 'pm', 'id', 'g9a', 'g9b', 'a4a', 'a4b', 'cr', 'sr1', 'sr2', 'pc', 'ibh', 'ibl', 'rc', 'fr')


def parse(text):
    """One report line -> dict of ints plus decoded fields, or None."""
    m = LINE.search(text.strip())
    if not m:
        return None
    r = {k: int(v, 16) for k, v in zip(NAMES, m.groups())}
    r['answered'] = bool(r['ibh'] & 2)              # a PHY pulled TA low on the last BMSR read
    r['inband_seen'] = bool(r['ibh'] & 1)
    r['link'] = r['answered'] and bool(r['sr2'] & 0x0004)
    r['an_done'] = bool(r['sr2'] & 0x0020)
    pc = r['pc']
    r['speed'] = 1000 if pc & 0x40 else 100 if pc & 0x20 else 10 if pc & 0x10 else None
    r['full_duplex'] = bool(pc & 0x08)
    ib = r['ibl']
    r['ib_link'], r['ib_speed'], r['ib_fd'] = bool(ib & 1), (10, 100, 1000, None)[(ib >> 1) & 3], bool(ib & 8)
    return r


def describe(r, mclk_hz=None, win_log2=FULL['WIN_LOG2']):
    s = (f"n={r['n']} retries={r['rt']} phys@{[a for a in range(32) if r['pm'] >> a & 1]} id={r['id']:08X} "
         f"link={'up' if r['link'] else 'down'} speed={r['speed']} fd={r['full_duplex']} "
         f"in-band link={r['ib_link']}{' ' + str(r['ib_speed']) if r['ib_link'] else ''} frames={r['fr']}")
    if mclk_hz:
        s += f" rxc~{r['rc'] * mclk_hz / 2 ** win_log2 / 1e6:.2f} MHz"
    return s


# ------------------------------------------------------------------ static
def static():
    bad = 0

    def check(name, ok, detail):
        nonlocal bad
        bad += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {name:<34} {detail}")

    print('--static: full-size parameters against the KSZ9031RNX, at the slowest and fastest CFGMCLK')
    for f in CFGMCLK_HZ:
        print(f'  CFGMCLK {f / 1e6:.1f} MHz')
        t_rst = 2 ** FULL['RST_LOG2'] / f
        t_wait = 2 ** FULL['WAIT_LOG2'] / f
        mdc = f / 2 ** FULL['MDC_LOG2']
        poll = 2 ** FULL['POLL_LOG2'] / f
        rc125 = 125e6 * 2 ** FULL['WIN_LOG2'] / f
        check('PHY reset pulse >= 10 ms', t_rst >= RESET_MIN_S, f'{t_rst * 1e3:.2f} ms')
        check('reset release to MDIO >= 100 us', t_wait >= MDIO_WAIT_MIN_S, f'{t_wait * 1e3:.2f} ms')
        check('MDC <= 2.5 MHz', mdc <= MDC_MAX_HZ, f'{mdc / 1e6:.3f} MHz')
        check('125 MHz RXC count fits rc (24 bit)', rc125 < 2 ** 24, f'{rc125:.0f} < {2 ** 24}')
        check('poll period', 0.3 <= poll <= 1.0, f'{poll * 1e3:.0f} ms; no link for {FULL["NOLINK_POLLS"] * poll:.1f} s -> reset')
        print(f'  info UART rate (same divider as the node)  {f / FULL["BAUD_DIV"]:.0f} baud')
    print('  note: the node on this board runs the same BAUD_DIV 60 at host rate 1144744; E2 inherits it')
    return bad


# ------------------------------------------------------------------ simulation
def run(cmd, **kw):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, **kw)


def gate_netlist():
    os.makedirs(WORK, exist_ok=True)
    out = f'{WORK}/gate.v'
    chp = ' '.join(f'-set {k} {v}' for k, v in SCALED.items())
    script = (f'read_verilog {RTL}; chparam {chp} eth_phy_status_ax7203; {SYNTH}; '
              f'setundef -zero -params; write_verilog -noattr {out}')
    t = time.time()
    p = run(['yosys', '-q', '-p', script])
    if p.returncode != 0:
        print(p.stdout[-2000:], p.stderr[-2000:])
        raise SystemExit('yosys failed')
    print(f'  netlist {out} ({time.time() - t:.1f} s): {SYNTH} with {chp}')
    return out


def simulate(gate, never_link, lines=6):
    os.makedirs(WORK, exist_ok=True)
    tag = f"{'gate' if gate else 'rtl'}_{'nolink' if never_link else 'link'}"
    exe = f'{WORK}/{tag}.vvp'
    src = [TB, MODEL, gate if gate else RTL, MOCK, CELLS]
    cmd = ['iverilog', '-g2012', '-o', exe, '-s', 'eth_phy_status_tb',
           f'-Peth_phy_status_tb.NEVER_LINK={int(never_link)}', f'-Peth_phy_status_tb.LINES={lines}']
    if gate:
        cmd.append('-DGATE')
    p = run(cmd + src)
    if p.returncode != 0:
        print(p.stderr[-3000:])
        raise SystemExit(f'iverilog failed ({tag})')
    t = time.time()
    p = run(['vvp', '-n', exe])
    out = p.stdout
    with open(f'{WORK}/{tag}.txt', 'w') as fh:
        fh.write(out)
    return tag, out, time.time() - t


def judge(tag, out, never_link, gate):
    bad = []
    tb = re.search(r'TB model_errors=(\d+) mdio_frames=(\d+) mdio_x=(\d+) contention=(\d+) '
                   r'tx_nonzero=(\d+) uart_framing=(\d+) lines=(\d+)', out)
    if not tb:
        return [f'no TB summary line ({"timeout" if "TB TIMEOUT" in out else "crash"})'], None
    errs, frames, mx, cont, txnz, frm, nl = map(int, tb.groups())
    for name, v in (('model_errors', errs), ('mdio_x', mx), ('contention', cont),
                    ('tx_nonzero', txnz), ('uart_framing', frm)):
        if v:
            bad.append(f'{name}={v}')
    reps = [parse(l[5:]) for l in out.splitlines() if l.startswith('UART|')]
    if not reps or any(r is None for r in reps):
        bad.append('a UART line does not parse')
        return bad, tb.group(0)
    if [r['n'] for r in reps] != list(range(1, len(reps) + 1)):
        bad.append(f"n not 1..{len(reps)}: {[r['n'] for r in reps]}")
    for r in reps:
        if r['pm'] != (1 << 0) | (1 << MODEL_ADDR):
            bad.append(f"n={r['n']} pm={r['pm']:08X}, want bits 0 and {MODEL_ADDR}")
        if r['id'] != PHYID:
            bad.append(f"n={r['n']} id={r['id']:08X}")
        if (r['g9a'], r['g9b'], r['a4a'], r['a4b']) != (0x0300, 0x0000, 0x01E1, 0x0181):
            bad.append(f"n={r['n']} advertisement g9 {r['g9a']:04X}>{r['g9b']:04X} a4 {r['a4a']:04X}>{r['a4b']:04X}")
        if not r['answered'] or not r['inband_seen']:
            bad.append(f"n={r['n']} ib={r['ibh']:X}{r['ibl']:X}: PHY did not answer or no in-band status")
    win_s = 2 ** SCALED['WIN_LOG2'] * TB_MCLK_NS * 1e-9
    last = reps[-1]
    if never_link:
        want_rt = [(r['n'] - 1) // SCALED['NOLINK_POLLS'] for r in reps]
        if [r['rt'] for r in reps] != want_rt:
            bad.append(f"rt {[r['rt'] for r in reps]}, want {want_rt} (a reset every {SCALED['NOLINK_POLLS']} polls)")
        if any(r['link'] or r['ib_link'] or r['fr'] for r in reps):
            bad.append('a line shows a link or a frame on a PHY that never links')
        rxc_hz = 125e6
    else:
        if any(r['rt'] for r in reps):
            bad.append('rt counted a retry on a PHY that links')
        if not (last['link'] and last['an_done'] and last['speed'] == 100 and last['full_duplex']):
            bad.append(f"last line not 100FD with link: sr2={last['sr2']:04X} pc={last['pc']:04X}")
        if not (last['ib_link'] and last['ib_speed'] == 100 and last['ib_fd']):
            bad.append(f"last in-band nibble {last['ibl']:X}, want B (link, 100, FD)")
        if last['fr'] == 0:
            bad.append('no frame start counted')
        rxc_hz = 25e6
    want_rc = rxc_hz * win_s
    if abs(last['rc'] - want_rc) > 2:
        bad.append(f"rc={last['rc']} RXC edges per window, want {want_rc:.1f} +-2")
    summary = f"{tb.group(0)}\n    last: {describe(last, 1e9 / TB_MCLK_NS, SCALED['WIN_LOG2'])}"
    if gate:
        summary += '\n    (contention is counted in the RTL run only: the netlist has no mdio_oe to probe)'
    return bad, summary


def sim(gate):
    print(f"--{'gate' if gate else 'sim'}: {'yosys netlist' if gate else 'RTL'} against the KSZ9031 status model")
    design = gate_netlist() if gate else None
    fails = 0
    for never_link in (False, True):
        tag, out, secs = simulate(design, never_link)
        bad, summary = judge(tag, out, never_link, gate)
        print(f"  {'PASS' if not bad else 'FAIL'} {tag:<12} {secs:6.1f} s  {summary or ''}")
        for b in bad:
            print(f'       {b}')
        fails += bool(bad)
    return fails


# ------------------------------------------------------------------ board
def read_port(port, baud, count):
    import serial  # pyserial; only this path needs it
    mid = sum(CFGMCLK_HZ) / 2
    print(f'reading {count} report lines from {port} at {baud} (E2 bitstream must be on the board)')
    with serial.Serial(port, baud, timeout=2) as ser:
        got, t0 = 0, time.time()
        while got < count and time.time() - t0 < count * 1.5 + 5:
            raw = ser.readline().decode('ascii', 'replace')
            r = parse(raw)
            if r:
                got += 1
                print(f'  {raw.strip()}\n    {describe(r, mid)}')
    return 0 if got == count else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--static', action='store_true')
    ap.add_argument('--sim', action='store_true')
    ap.add_argument('--gate', action='store_true')
    ap.add_argument('--parse', metavar='FILE')
    ap.add_argument('--port')
    ap.add_argument('--baud', type=int, default=1144744)
    ap.add_argument('--lines', type=int, default=6)
    a = ap.parse_args()
    if not (a.static or a.sim or a.gate or a.parse or a.port):
        a.static = a.sim = a.gate = True
    fails = 0
    if a.static:
        fails += static()
    if a.sim:
        fails += sim(False)
    if a.gate:
        fails += sim(True)
    if a.parse:
        with open(a.parse) as fh:
            for l in fh:
                r = parse(l)
                if r:
                    print(describe(r, sum(CFGMCLK_HZ) / 2))
    if a.port:
        fails += read_port(a.port, a.baud, a.lines)
    print('RESULT', 'PASS' if fails == 0 else f'FAIL ({fails})')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
