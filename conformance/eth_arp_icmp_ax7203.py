#!/usr/bin/env python3
"""Ethernet step E3: check fpga/vivado/eth_arp_icmp_ax7203.v (ARP + ping at 192.168.1.222).

    python3 conformance/eth_arp_icmp_ax7203.py              every gate below except --port; RESULT PASS/FAIL
    python3 conformance/eth_arp_icmp_ax7203.py --self-test  the checker's own frame code and verdicts (no simulator)
    python3 conformance/eth_arp_icmp_ax7203.py --static     full-size parameters against the KSZ9031 and the frames
    python3 conformance/eth_arp_icmp_ax7203.py --sim        RTL against formal/ksz9031_frame_model.v, every scenario
    python3 conformance/eth_arp_icmp_ax7203.py --gate       the same on yosys's netlist (RAMB36E1 from the mock below)
    python3 conformance/eth_arp_icmp_ax7203.py --parse F    decode report lines saved in a file
    python3 conformance/eth_arp_icmp_ax7203.py --port P     read the board  (NOT RUN: E3 is not flashed)
    python3 conformance/eth_arp_icmp_ax7203.py --judge      verdict on the board step from its six logs in
                                                            conformance/board_runs (H1..H4, CONFLICT, OTHER;
                                                            rules and numbers: specs/trinet/eth_arp_icmp_e3_ax7203.t27)

Every request frame is built here with struct and zlib.crc32, written into a stimulus file that
the PHY model plays on RXD, and every frame the design sends is compared byte for byte, preamble
to FCS, with the reply computed here from the request (the reference below is written from the
protocols, not from the RTL). Also checked per scenario: preamble 15 x 5 + D, padding to 60
bytes, FCS, idle nibbles between replies (>= 24, and exactly 24 where the timing forces it), the
report line's counters, E2's fields, and zero model errors (TX setup/hold at the PHY pins, TX_ER,
TXC period, MDIO). conformance/NODE_ETHERNET_PLAN.md, step E3, has the results.
"""
import argparse
import concurrent.futures
import os
import re
import struct
import subprocess
import sys
import time
import zlib

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RTL = 'fpga/vivado/eth_arp_icmp_ax7203.v'
TOP = 'eth_arp_icmp_ax7203'
TB = 'formal/eth_arp_icmp_tb.v'
TBTOP = 'eth_arp_icmp_tb'
MODEL = 'formal/ksz9031_frame_model.v'
MOCK = 'fpga/openxc7-synth/STARTUPE2_mock.v'
CELLS = '/opt/homebrew/share/yosys/xilinx/cells_sim.v'
# cells_sim.v's RAMB36E1 has ports and a specify block but no behaviour (its outputs float), so
# the gate run compiles a copy of cells_sim.v without it plus this behavioural one.
RAMB_MOCK = 'fpga/openxc7-synth/RAMB36E1_mock.v'
SYNTH = f'synth_xilinx -flatten -abc9 -nocarry -nodsp -nosrl -arch xc7 -top {TOP}'
WORK = '/tmp/e3sim'

# Full-size parameters (the RTL defaults) and the testbench's scaled ones.
FULL = dict(RST_LOG2=20, WAIT_LOG2=21, POLL_LOG2=25, WIN_LOG2=20, MDC_LOG2=5, BAUD_DIV=60, NOLINK_POLLS=30,
            SLOT_LOG2=11, TX_DLY=10)
SCALED = dict(RST_LOG2=6, WAIT_LOG2=7, POLL_LOG2=17, WIN_LOG2=12, NOLINK_POLLS=4)
TB_MCLK_NS = 14                       # STARTUPE2 mock period
CFGMCLK_HZ = (65.6e6, 68.7e6)         # measured range over the board chips (cp2102n-rate-grid)
RESET_MIN_S = 10e-3
MDIO_WAIT_MIN_S = 100e-6
MDC_MAX_HZ = 2.5e6
PHYID = 0x00221622
MODEL_ADDR = 1

# The design's identity (RTL parameters MAC, IP, TTL) and a host on the LAN.
MAC = bytes.fromhex('02005EF90001')
IP = bytes([192, 168, 1, 222])
TTL = 64
HOST_MAC = bytes.fromhex('3C22FB0A1B2C')
HOST_IP = bytes([192, 168, 1, 10])
BCAST = b'\xff' * 6
IFG_NIB = 24                          # 96 bit times
SLOT = 1 << FULL['SLOT_LOG2']
PRE = bytes([0x55] * 7 + [0xD5])

FIELD = r'([0-9A-F]{%d})'
LINE = re.compile(
    r'E3 n=%s rt=%s pm=%s id=%s g9=%s>%s a4=%s>%s cr=%s sr=%s/%s pc=%s ib=%s%s rc=%s fr=%s '
    r'rx=%s fe=%s ce=%s aq=%s ar=%s eq=%s er=%s ed=%s lk=%s$'
    % tuple(FIELD % w for w in (4, 2, 8, 8, 4, 4, 4, 4, 4, 4, 4, 4, 1, 1, 6, 4, 4, 4, 4, 4, 4, 4, 4, 4, 1)))
NAMES = ('n', 'rt', 'pm', 'id', 'g9_before', 'g9_after', 'a4_before', 'a4_after', 'cr', 'sr1', 'sr2', 'pc',
         'ibh', 'ibl', 'rc', 'fr', 'rx', 'fe', 'ce', 'aq', 'ar', 'eq', 'er', 'ed', 'lk')
WIDTH = dict(zip(NAMES, (4, 2, 8, 8, 4, 4, 4, 4, 4, 4, 4, 4, 1, 1, 6, 4, 4, 4, 4, 4, 4, 4, 4, 4, 1)))
COUNTERS = ('rx', 'fe', 'ce', 'aq', 'ar', 'eq', 'er')


def parse(text):
    """One report line -> dict of ints plus decoded fields, or None."""
    m = LINE.search(text.strip())
    if not m:
        return None
    r = {k: int(v, 16) for k, v in zip(NAMES, m.groups())}
    r['answered'] = bool(r['ibh'] & 2)
    r['inband_seen'] = bool(r['ibh'] & 1)
    r['link'] = r['answered'] and bool(r['sr2'] & 0x0004)
    r['an_done'] = bool(r['sr2'] & 0x0020)
    pc = r['pc']
    r['speed'] = 1000 if pc & 0x40 else 100 if pc & 0x20 else 10 if pc & 0x10 else None
    r['full_duplex'] = bool(pc & 0x08)
    ib = r['ibl']
    r['ib_link'], r['ib_speed'], r['ib_fd'] = bool(ib & 1), (10, 100, 1000, None)[(ib >> 1) & 3], bool(ib & 8)
    return r


def fmt_line(r):
    """The inverse of parse (used by --self-test)."""
    v = {k: ('%0*X' % (WIDTH[k], r.get(k, 0))) for k in NAMES}
    return ('E3 n={n} rt={rt} pm={pm} id={id} g9={g9_before}>{g9_after} a4={a4_before}>{a4_after} cr={cr} '
            'sr={sr1}/{sr2} pc={pc} ib={ibh}{ibl} rc={rc} fr={fr} rx={rx} fe={fe} ce={ce} aq={aq} ar={ar} '
            'eq={eq} er={er} ed={ed} lk={lk}'.format(**v))


def describe(r, mclk_hz=None, win_log2=FULL['WIN_LOG2']):
    speed, fd = (r['speed'], r['full_duplex']) if r['answered'] else ('-', '-')
    s = (f"n={r['n']} retries={r['rt']} id={r['id']:08X} link={'up' if r['link'] else 'down'} "
         f"speed={speed} fd={fd} in-band={r['ibl']:X} tx_enabled={r['lk']} "
         + ' '.join(f'{k}={r[k]}' for k in COUNTERS + ('ed',)))
    if mclk_hz:
        s += f" rxc~{r['rc'] * mclk_hz / 2 ** win_log2 / 1e6:.2f} MHz"
    return s


# ------------------------------------------------------------------ frames
def csum16(data):
    """Internet checksum (RFC 1071) of data: the value to put in the field."""
    if len(data) % 2:
        data += b'\0'
    s = sum(struct.unpack('!%dH' % (len(data) // 2), data))
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return ~s & 0xFFFF


def fcs(frame):
    return struct.pack('<I', zlib.crc32(frame) & 0xFFFFFFFF)


def ether(dst, src, etype, payload, pad=b''):
    """Frame without preamble, padded to 60 bytes (with `pad` bytes first, then zeros), plus FCS."""
    f = dst + src + struct.pack('!H', etype) + payload + pad
    f += b'\0' * max(0, 60 - len(f))
    return f + fcs(f)


def arp(oper, sha, spa, tha, tpa):
    return struct.pack('!HHBBH', 1, 0x0800, 6, 4, oper) + sha + spa + tha + tpa


def ipv4(src, dst, proto, body, ident=0x1234, flags=0x0000, ttl=64, tos=0, opts=b'', bad_csum=False):
    ihl = 5 + len(opts) // 4
    h = struct.pack('!BBHHHBBH4s4s', 0x40 | ihl, tos, 4 * ihl + len(body), ident, flags, ttl, proto, 0, src, dst) + opts
    c = csum16(h) ^ (0x0001 if bad_csum else 0)
    return h[:10] + struct.pack('!H', c) + h[12:] + body


def icmp(typ, code, ident, seq, data, bad_csum=False):
    m = struct.pack('!BBHHH', typ, code, 0, ident, seq) + data
    c = csum16(m) ^ (0x0100 if bad_csum else 0)
    return m[:2] + struct.pack('!H', c) + m[4:]


def ping_data(n, seed=0):
    return bytes((seed + 7 * i + (i >> 3)) & 0xFF for i in range(n))


def arp_request(tpa=IP, dst=BCAST, sha=HOST_MAC, spa=HOST_IP):
    return ether(dst, sha, 0x0806, arp(1, sha, spa, b'\0' * 6, tpa))


def echo_request(n, dst_ip=IP, dst_mac=MAC, ident=0x4A21, seq=1, **kw):
    ip_kw = {k: kw.pop(k) for k in ('ident_ip', 'flags', 'tos', 'opts', 'ip_bad', 'proto') if k in kw}
    body = icmp(kw.pop('typ', 8), 0, ident, seq, ping_data(n, seq), bad_csum=kw.pop('icmp_bad', False))
    ip = ipv4(HOST_IP, dst_ip, ip_kw.get('proto', 1), body, ident=ip_kw.get('ident_ip', 0x1234 + seq),
              flags=ip_kw.get('flags', 0x4000), tos=ip_kw.get('tos', 0), opts=ip_kw.get('opts', b''),
              bad_csum=ip_kw.get('ip_bad', False))
    return ether(dst_mac, kw.pop('src_mac', HOST_MAC), kw.pop('etype', 0x0800), ip, pad=kw.pop('pad', b''))


# ------------------------------------------------------------------ reference
def reference(frame, odd_nibble=False):
    """What a responder at MAC/IP must do with one received frame (bytes incl. FCS).

    Returns (counts, reply): counts has keys fe, ce, aq, eq (0/1); reply is the frame to send
    (without preamble, with FCS), or None. Written from RFC 826 / 791 / 792, not from the RTL.
    """
    c = dict(fe=0, ce=0, aq=0, eq=0)
    if odd_nibble or len(frame) < 64 or zlib.crc32(frame) & 0xFFFFFFFF != 0x2144DF1C:
        c['fe'] = 1                                         # 0x2144DF1C: CRC-32 over data + FCS
        return c, None
    data = frame[:-4]
    dst, src, etype = data[0:6], data[6:12], struct.unpack('!H', data[12:14])[0]
    if etype == 0x0806 and dst in (MAC, BCAST):
        htype, ptype, hlen, plen, oper = struct.unpack('!HHBBH', data[14:22])
        sha, spa, tpa = data[22:28], data[28:32], data[38:42]
        if (htype, ptype, hlen, plen, oper) == (1, 0x0800, 6, 4, 1) and tpa == IP:
            c['aq'] = 1
            return c, ether(sha, MAC, 0x0806, arp(2, MAC, IP, sha, spa))
        return c, None
    if etype != 0x0800 or dst != MAC or data[14] != 0x45:
        return c, None
    hdr = data[14:34]
    if csum16(hdr) != 0:
        c['ce'] = 1
        return c, None
    tos, tl, ident, ff, ttl, proto = struct.unpack('!xBHHHBB', hdr[:10])
    if hdr[16:20] != IP or proto != 1 or ff & 0x3FFF:
        return c, None
    if tl < 28 or 14 + tl > len(data) or 14 + tl > SLOT or data[34:36] != b'\x08\x00':
        return c, None
    msg = data[34:14 + tl]
    if csum16(msg) != 0:
        c['ce'] = 1
        return c, None
    c['eq'] = 1
    body = b'\0\0' + b'\0\0' + msg[4:]
    body = body[:2] + struct.pack('!H', csum16(body)) + body[4:]
    h = struct.pack('!BBHHHBBH4s4s', 0x45, tos, tl, ident, ff, TTL, 1, 0, IP, hdr[12:16])
    h = h[:10] + struct.pack('!H', csum16(h)) + h[12:]
    return c, ether(src, MAC, 0x0800, h + body)


# ------------------------------------------------------------------ scenarios
def F(frame, gap=200, odd=None, pre=PRE):
    """One received frame: wire bytes after the preamble, idle nibbles after it, an extra lone nibble."""
    return dict(frame=frame, gap=gap, odd=odd, pre=pre)


def scenarios():
    S = []

    def sc(name, what, frames, **kw):
        S.append(dict(name=name, what=what, frames=frames, **kw))

    sc('arp_us', 'ARP who-has 192.168.1.222, broadcast and unicast (cache refresh): exact replies',
       [F(arp_request()), F(arp_request(dst=MAC))])
    sc('arp_other', 'ARP who-has 192.168.1.1, and a request for us sent to another MAC: no TX',
       [F(arp_request(tpa=bytes([192, 168, 1, 1]))), F(arp_request(dst=bytes.fromhex('02005EF90002')))])
    sc('icmp_56', 'ping with the default 56-byte payload: exact reply', [F(echo_request(56))])
    bad = bytearray(echo_request(56))
    bad[-1] ^= 0x01
    bad2 = bytearray(arp_request())
    bad2[30] ^= 0x10
    runt = HOST_MAC + MAC + b'\x08\x00' + bytes(40)
    sc('bad_fcs', 'bad FCS (ICMP), a data bit flipped (ARP), a 58-byte runt with a good CRC, '
       'a good frame plus a dribble nibble: no TX, fe=4',
       [F(bytes(bad)), F(bytes(bad2)), F(runt + fcs(runt)), F(echo_request(56, seq=2), odd=0x7)])
    sc('not_for_us', 'ICMP to another IP, to our IP at another MAC, to broadcast; UDP, echo reply, '
       'a fragment, IP options, IPv6 ethertype: no TX',
       [F(echo_request(56, dst_ip=bytes([192, 168, 1, 223]))),
        F(echo_request(56, dst_mac=bytes.fromhex('02005EF90002'))),
        F(echo_request(56, dst_mac=BCAST)),
        F(echo_request(56, proto=17)),
        F(echo_request(56, typ=0)),
        F(echo_request(56, flags=0x2000)),
        F(echo_request(56, opts=b'\x01\x01\x01\x00')),
        F(echo_request(56, etype=0x86DD))])
    sc('back_to_back', 'ARP then ICMP 12 bytes apart (minimum IFG): both answered, in order',
       [F(arp_request(), gap=IFG_NIB), F(echo_request(56))])
    sc('icmp_large', 'ping -s 1000 and -s 1472 (full 1500-byte datagram): exact replies',
       [F(echo_request(1000, seq=3)), F(echo_request(1472, seq=4), gap=400)])
    sc('icmp_small', 'ping -s 0 with junk in the request padding, -s 17 (odd ICMP length), -s 18, and '
       'a request after a shortened preamble (55 D5): padding and checksums',
       [F(echo_request(0, seq=5, pad=b'\xAA' * 10)), F(echo_request(17, seq=6)), F(echo_request(18, seq=7)),
        F(echo_request(56, seq=8), pre=bytes([0x55, 0xD5]))])
    # The buffer rule (header of the RTL): two 2 KB slots; a request is stored if a slot is free at its
    # SFD, and a slot stays busy until its reply's last FCS nibble. At line rate, with every reply as
    # long as its request, that never drops as long as no request is shorter than the reply sent before
    # it: a run of equal requests at minimum IFG goes out at exactly minimum IFG, reply k+1 held by
    # the 24-nibble gap and by the end of request k+1 at the same nibble. min_ifg checks that; the
    # next scenario checks the case that does drop, worked out by hand in nibbles (ARP 144 on the wire,
    # ICMP-56 220, gap 24, L = the design's latency, any L < 64):
    #   a0 SFD 16 -> slot 0; i1 SFD 184 -> slot 1; a0 reply ends 288+L, so a2 SFD 428 -> slot 0;
    #   i1 reply 388+L..608+L, a2 reply queued behind it (exactly 24 idle nibbles), 632+L..776+L;
    #   i3 SFD 596: slot 1 sends i1, slot 0 holds a2 -> dropped (eq counts it, er does not);
    #   a4 SFD 840 -> slot 1, i5 SFD 1008 -> slot 0: both answered.
    sc('min_ifg', 'four ARP requests then four pings (-s 56), all 12 bytes apart: all answered, '
       'replies within each run exactly 12 bytes apart',
       [F(arp_request() if i < 4 else echo_request(56, seq=10 + i), gap=IFG_NIB) for i in range(8)],
       queued=[1, 2, 3, 5, 6, 7])
    sc('min_ifg_drop', 'ARP, ping, ARP, ping, ARP, ping at minimum IFG: the 4th request starts while '
       'the ping reply is sent and the ARP reply waits: dropped and counted; the rest exact',
       [F(arp_request() if i % 2 == 0 else echo_request(56, seq=30 + i), gap=IFG_NIB) for i in range(6)],
       answered=[0, 1, 2, 4, 5], queued=[2])
    sc('bad_csum', 'good FCS, bad IPv4 header checksum; good header, bad ICMP checksum: no TX, ce=2',
       [F(echo_request(56, ip_bad=True)), F(echo_request(56, icmp_bad=True, seq=2))])
    sc('overflow', 'ping -s 1000 then two -s 56 at minimum IFG: the third finds both slots busy; '
       'the second reply follows the first after exactly 24 idle nibbles',
       [F(echo_request(1000, seq=20), gap=IFG_NIB), F(echo_request(56, seq=21), gap=IFG_NIB),
        F(echo_request(56, seq=22))], answered=[0, 1], queued=[1])
    sc('rxd_late_8ns', 'RXD/RX_CTL 8 ns after RXC: replies exact from the falling-edge sample; ed > 0',
       [F(arp_request()), F(echo_request(56))], tb=dict(RXD_DLY_PS=8000), ed='>0')
    sc('rxc_late_15ns', 'RXC 15 ns after RXD: replies exact',
       [F(arp_request()), F(echo_request(56))], tb=dict(RXC_DLY_PS=15000))
    sc('nolink', 'the PHY never links (RXC 125 MHz, in-band 0): requests counted, nothing sent, lk=0',
       [F(arp_request()), F(echo_request(56))], tb=dict(NEVER_LINK=1), link=False)
    sc('tx_skew_zero', 'NEGATIVE: TXD changes on the TXC falling edge (no LUT delay): the model '
       'must report setup/hold or TX_ER errors', [F(echo_request(56))], tb=dict(TXD_DLY_PS=0), negative=True)
    return S


def stim_words(frames):
    w = ['1020']                                            # 32 idle nibbles first
    for f in frames:
        w += ['00%02X' % b for b in f['pre'] + f['frame']]
        if f['odd'] is not None:
            w.append('300%X' % f['odd'])
        g = f['gap']
        while g > 0:
            w.append('1%03X' % min(g, 0xFFF))
            g -= min(g, 0xFFF)
    w.append('F000')
    return w


def expect(sc):
    """Expected replies (in order), counters, reply indexes with exactly 24 idle nibbles, and the
    request index each reply answers."""
    replies, cnt = [], dict(rx=0, fe=0, ce=0, aq=0, ar=0, eq=0, er=0)
    for f in sc['frames']:
        c, rep = reference(f['frame'], f['odd'] is not None)
        cnt['rx'] += 1
        for k in c:
            cnt[k] += c[k]
        replies.append(rep)
    answered = sc.get('answered', [i for i, r in enumerate(replies) if r is not None])
    if not sc.get('link', True):
        answered = []
    out = [replies[i] for i in answered]
    for i in answered:
        cnt['ar' if replies[i][12:14] == b'\x08\x06' else 'er'] += 1
    queued = [answered.index(i) for i in sc.get('queued', [])]
    return out, cnt, queued, answered


# ------------------------------------------------------------------ judge
TXF = re.compile(r'^TXF t=(\d+) ifg=(\d+) nib=(\d+) data=([0-9a-fx]*)$', re.M)
TBSUM = re.compile(r'TB model_errors=(\d+) mdio_frames=(\d+) mdio_x=(\d+) tx_frames=(\d+) '
                   r'uart_framing=(\d+) lines=(\d+)')


def tx_frames(out):
    """TXF lines -> list of (t_ns, ifg_nibbles, bytes or None, problems)."""
    res = []
    for m in TXF.finditer(out):
        t, ifg, nib, s = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
        prob = []
        if len(s) != nib:
            prob.append(f'nib={nib} but {len(s)} nibbles printed')
        if 'x' in s:
            prob.append('X on TXD')
            res.append((t, ifg, None, prob))
            continue
        if s[:16] != '5' * 15 + 'd':
            prob.append(f'preamble/SFD {s[:16]}')
        body = s[16:]
        if len(body) % 2:
            prob.append(f'{len(body)} data nibbles, not whole bytes')
            body = body[:-1]
        data = bytes(int(body[i + 1] + body[i], 16) for i in range(0, len(body), 2))  # low nibble first
        res.append((t, ifg, data, prob))
    return res


def judge(sc, out):
    bad = []
    neg = sc.get('negative', False)
    link = sc.get('link', True)
    tb = TBSUM.search(out)
    if not tb:
        return [f'no TB summary line ({"timeout" if "TB TIMEOUT" in out else "crash"})'], None
    errs, mframes, mx, ntx, frm, nl = map(int, tb.groups())
    if neg:
        return ([] if errs > 0 else [f'model_errors=0: the model did not flag data changing on the TXC edge']), \
            f'{tb.group(0)}  (negative test: errors expected)'
    for name, v in (('model_errors', errs), ('mdio_x', mx), ('uart_framing', frm)):
        if v:
            bad.append(f'{name}={v}')
    want, cnt, queued, answered = expect(sc)
    got = tx_frames(out)
    if ntx != len(got):
        bad.append(f'model counted {ntx} TX frames, {len(got)} TXF lines')
    if len(got) != len(want):
        bad.append(f'{len(got)} frames sent, want {len(want)}')
    for i, ((t, ifg, data, prob), w) in enumerate(zip(got, want)):
        for p in prob:
            bad.append(f'TX frame {i}: {p}')
        if data is None:
            continue
        if data != w:
            k = next((j for j in range(min(len(data), len(w))) if data[j] != w[j]), min(len(data), len(w)))
            bad.append(f'TX frame {i}: {len(data)} bytes, want {len(w)}; first difference at byte {k}: '
                       f'got {data[k:k + 8].hex()} want {w[k:k + 8].hex()}')
        if len(data) < 64:
            bad.append(f'TX frame {i}: {len(data)} bytes, below 64')
        if zlib.crc32(data) & 0xFFFFFFFF != 0x2144DF1C:
            bad.append(f'TX frame {i}: FCS wrong')
        if i > 0 and ifg < IFG_NIB:
            bad.append(f'TX frame {i}: {ifg} idle nibbles before it, below {IFG_NIB}')
        if i in queued and ifg != IFG_NIB:
            bad.append(f'TX frame {i}: {ifg} idle nibbles before it, want exactly {IFG_NIB} (queued reply)')
    reps = [parse(l[5:]) for l in out.splitlines() if l.startswith('UART|')]
    if not reps or any(r is None for r in reps):
        bad.append('no UART line, or one does not parse')
        return bad, tb.group(0)
    if [r['n'] for r in reps] != list(range(1, len(reps) + 1)):
        bad.append(f"n not 1..{len(reps)}: {[r['n'] for r in reps]}")
    last = reps[-1]
    for r in reps:
        if r['pm'] != (1 << 0) | (1 << MODEL_ADDR) or r['id'] != PHYID:
            bad.append(f"n={r['n']} pm={r['pm']:08X} id={r['id']:08X}")
        if (r['g9_before'], r['g9_after'], r['a4_before'], r['a4_after']) != (0x0300, 0x0000, 0x01E1, 0x0181):
            bad.append(f"n={r['n']} advertisement g9 {r['g9_before']:04X}>{r['g9_after']:04X} "
                       f"a4 {r['a4_before']:04X}>{r['a4_after']:04X}")
    got_c = {k: last[k] for k in COUNTERS}
    if got_c != cnt:
        bad.append(f'counters {got_c}, want {cnt}')
    if link:
        if not (last['link'] and last['speed'] == 100 and last['full_duplex'] and last['ibl'] == 0xB):
            bad.append(f"last line not 100FD with in-band B: sr2={last['sr2']:04X} pc={last['pc']:04X} ib={last['ibl']:X}")
        if last['lk'] != 1:
            bad.append('lk=0 on a linked PHY')
        want_rc = 25e6 * 2 ** SCALED['WIN_LOG2'] * TB_MCLK_NS * 1e-9
        if abs(last['rc'] - want_rc) > 2:
            bad.append(f"rc={last['rc']}, want {want_rc:.1f} +-2")
    else:
        if last['lk'] != 0 or any(r['link'] for r in reps):
            bad.append('lk=1 or link up on a PHY that never links')
    if sc.get('ed') == '>0':
        if last['ed'] == 0:
            bad.append('ed=0: expected rising-edge samples to disagree with falling-edge ones')
    elif last['ed'] != 0:
        bad.append(f"ed={last['ed']}, want 0")
    ifgs = [g[1] for g in got[1:]]
    # latency: end of the request on RXD to the first preamble nibble on TXD, in 40 ns nibbles
    rxe = [int(t) for t in re.findall(r'^RXE t=(\d+)$', out, re.M)]
    lat = sorted({round((g[0] - rxe[a]) / 40) for g, a in zip(got, answered) if a < len(rxe)})
    summary = (f"tx={len(got)} " + ' '.join(f'{k}={last[k]}' for k in COUNTERS + ('ed', 'lk'))
               + (f' ifg={ifgs}' if ifgs else '') + (f' lat={lat}' if lat else '') + f' model_errors={errs}')
    return bad, summary


# ------------------------------------------------------------------ simulation
def run(cmd, **kw):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, **kw)


def gate_netlist():
    os.makedirs(WORK, exist_ok=True)
    out = f'{WORK}/gate.v'
    chp = ' '.join(f'-set {k} {v}' for k, v in SCALED.items())
    script = (f'read_verilog {RTL}; chparam {chp} {TOP}; {SYNTH}; '
              f'setundef -zero -params; stat; write_verilog -noattr {out}')
    t = time.time()
    p = run(['yosys', '-p', script])
    if p.returncode != 0:
        print(p.stdout[-2000:], p.stderr[-2000:])
        raise SystemExit('yosys failed')
    cells = re.findall(r'^\s+(\d+)\s+(RAMB\w+|FD\w+|LUT\d|BUFG|IOBUF)\s*$', p.stdout, re.M)
    print(f'  netlist {out} ({time.time() - t:.1f} s): {SYNTH} with {chp}')
    print('  cells  ' + ' '.join(f'{n} {c}' for n, c in cells[-12:]))
    return out


def cells_without_ramb36():
    """Copy of cells_sim.v minus its behaviour-less RAMB36E1, for the gate run."""
    text = open(CELLS).read()
    m = re.search(r'^module RAMB36E1 \(.*?^endmodule\n', text, re.M | re.S)
    if not m or 'always' in m.group(0):
        raise SystemExit(f'{CELLS}: RAMB36E1 not found, or it has behaviour now; revisit {RAMB_MOCK}')
    out = f'{WORK}/cells_sim_no_ramb36e1.v'
    with open(out, 'w') as fh:
        fh.write(text[:m.start()] + text[m.end():])
    return out


def simulate(sc, design):
    tag = f"{'gate' if design else 'rtl'}_{sc['name']}"
    exe, stim = f'{WORK}/{tag}.vvp', f'{WORK}/{sc["name"]}.hex'
    with open(stim, 'w') as fh:
        fh.write('\n'.join(stim_words(sc['frames'])) + '\n')
    cmd = ['iverilog', '-g2012', '-o', exe, '-s', TBTOP]
    cmd += [f'-P{TBTOP}.{k}={v}' for k, v in sc.get('tb', {}).items()]
    if design:
        cmd.append('-DGATE')
    cells = [f'{WORK}/cells_sim_no_ramb36e1.v', RAMB_MOCK] if design else [CELLS]
    p = run(cmd + [TB, MODEL, design or RTL, MOCK] + cells)
    if p.returncode != 0:
        return tag, 'iverilog failed:\n' + p.stderr[-3000:], 0.0
    t = time.time()
    p = run(['vvp', '-n', exe, f'+STIM={stim}'])
    with open(f'{WORK}/{tag}.txt', 'w') as fh:
        fh.write(p.stdout)
    return tag, p.stdout, time.time() - t


def sim(gate, only=None, jobs=6):
    print(f"--{'gate' if gate else 'sim'}: {'yosys netlist' if gate else 'RTL'} against the KSZ9031 frame model")
    os.makedirs(WORK, exist_ok=True)
    design = gate_netlist() if gate else None
    if gate:
        cells_without_ramb36()
    scs = [s for s in scenarios() if not only or s['name'] in only]
    fails = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = {s['name']: ex.submit(simulate, s, design) for s in scs}
        for s in scs:
            tag, out, secs = futs[s['name']].result()
            bad, summary = judge(s, out)
            print(f"  {'PASS' if not bad else 'FAIL'} {s['name']:<14} {secs:6.1f} s  {summary or ''}")
            for b in bad[:12]:
                print(f'       {b}')
            fails += bool(bad)
    return fails


# ------------------------------------------------------------------ static
def static():
    bad = 0

    def check(name, ok, detail):
        nonlocal bad
        bad += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {name:<38} {detail}")

    print('--static: full-size parameters against the KSZ9031RNX, at the slowest and fastest CFGMCLK')
    for f in CFGMCLK_HZ:
        print(f'  CFGMCLK {f / 1e6:.1f} MHz')
        check('PHY reset pulse >= 10 ms', 2 ** FULL['RST_LOG2'] / f >= RESET_MIN_S,
              f"{2 ** FULL['RST_LOG2'] / f * 1e3:.2f} ms")
        check('reset release to MDIO >= 100 us', 2 ** FULL['WAIT_LOG2'] / f >= MDIO_WAIT_MIN_S,
              f"{2 ** FULL['WAIT_LOG2'] / f * 1e3:.2f} ms")
        check('MDC <= 2.5 MHz', f / 2 ** FULL['MDC_LOG2'] <= MDC_MAX_HZ, f"{f / 2 ** FULL['MDC_LOG2'] / 1e6:.3f} MHz")
        check('125 MHz RXC count fits rc (24 bit)', 125e6 * 2 ** FULL['WIN_LOG2'] / f < 2 ** 24, '')
        poll = 2 ** FULL['POLL_LOG2'] / f
        line_s = 189 * 10 * FULL['BAUD_DIV'] / f
        check('report line fits in one poll period', line_s < poll, f'{line_s * 1e3:.2f} ms < {poll * 1e3:.0f} ms')
    print('  frames')
    big = 14 + 20 + 8 + 1472
    check('largest ping (1500-byte datagram) fits a slot', big <= SLOT, f'{big} <= {SLOT} bytes')
    check('slot holds the whole ARP request', 42 <= SLOT, '')
    check('IFG >= 96 bit times', IFG_NIB * 4 >= 96, f'{IFG_NIB} nibbles')
    wrap = 2 ** 16 / (100e6 / 8 / (64 + 20))
    print(f'  info 16-bit counters wrap after {wrap:.2f} s of minimum-size frames at 100M '
          f'(report every {2 ** FULL["POLL_LOG2"] / CFGMCLK_HZ[1]:.2f}-{2 ** FULL["POLL_LOG2"] / CFGMCLK_HZ[0]:.2f} s): '
          'a flood can wrap them between two lines; a ping cannot')
    print(f'  info buffer 2 x {SLOT} bytes = 32 Kib = one RAMB36 (E2 and the node use no BRAM)')
    return bad


# ------------------------------------------------------------------ self-test
def self_test():
    bad = 0

    def check(name, ok):
        nonlocal bad
        bad += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")

    print('--self-test: the checker\'s own frame code and verdicts, no simulator')
    # CRC: the RTL's nibble-serial register (reflected, init ~0, low nibble first) against zlib
    def crc_nib(c, d):
        for k in range(4):
            c = (c >> 1) ^ 0xEDB88320 if (c ^ (d >> k)) & 1 else c >> 1
        return c
    f = echo_request(56)
    c = 0xFFFFFFFF
    for b in f[:-4]:
        c = crc_nib(crc_nib(c, b & 15), b >> 4)
    check('nibble CRC-32, complemented, equals zlib.crc32', (~c & 0xFFFFFFFF) == zlib.crc32(f[:-4]))
    for b in f[-4:]:
        c = crc_nib(crc_nib(c, b & 15), b >> 4)
    check('residue after the FCS is 0xDEBB20E3 (the RTL test)', c == 0xDEBB20E3)
    check('zlib.crc32 over frame + FCS is 0x2144DF1C (this checker\'s test)', zlib.crc32(f) == 0x2144DF1C)
    hdr = bytes.fromhex('450000730000400040110000c0a80001c0a800c7')
    check('IPv4 header checksum of a textbook header is 0xB861', csum16(hdr) == 0xB861)
    arp_rep = reference(arp_request())[1]
    want = bytes.fromhex('3c22fb0a1b2c 02005ef90001 0806 0001 0800 0604 0002 02005ef90001 c0a801de '
                         '3c22fb0a1b2c c0a8010a'.replace(' ', '')) + bytes(18)
    check('ARP reply to who-has 192.168.1.222, hand-written', arp_rep == want + fcs(want))
    q = echo_request(56)
    r = reference(q)[1]
    check('echo reply: same id, sequence and payload, type 0, addresses swapped',
          r[38:98] == q[38:98] and r[34] == 0 and r[26:30] == IP and r[30:34] == HOST_IP and r[0:6] == HOST_MAC)
    check('echo reply: IP and ICMP checksums verify', csum16(r[14:34]) == 0 and csum16(r[34:98]) == 0)
    check('echo reply to ping -s 0 is padded with zeros, not the request\'s padding',
          reference(echo_request(0, pad=b'\xAA' * 10))[1][42:60] == bytes(18))
    check('bad FCS -> fe, no reply', reference(bytes(bytearray(q[:-1]) + bytes([q[-1] ^ 1]))) == (
        dict(fe=1, ce=0, aq=0, eq=0), None))
    check('bad IP checksum -> ce', reference(echo_request(56, ip_bad=True))[0]['ce'] == 1)
    check('bad ICMP checksum -> ce', reference(echo_request(56, icmp_bad=True))[0]['ce'] == 1)
    check('ICMP to another IP -> nothing', reference(echo_request(56, dst_ip=HOST_IP)) == (
        dict(fe=0, ce=0, aq=0, eq=0), None))
    rep = dict(n=1, pm=3, id=PHYID, g9_before=0x300, a4_before=0x1E1, a4_after=0x181, sr2=0x796D, pc=0x28,
               ibh=3, ibl=0xB, rc=0x05B8, rx=0x12, fe=1, aq=2, ar=2, eq=0xABC, er=0xABC, lk=1)
    r2 = parse('noise ' + fmt_line(rep) + '\r\n')
    check('report line: format -> parse round trip', r2 is not None and all(r2[k] == v for k, v in rep.items()))
    check('report line is 187 characters + CR LF', len(fmt_line(rep)) + 2 == 189)
    # the judge on made-up simulator output: right, then wrong in one detail each
    sc = [s for s in scenarios() if s['name'] == 'overflow'][0]
    want, cnt, queued, _ = expect(sc)

    def fake(frames, ifgs, cnts, errors=0, pre='5' * 15 + 'd'):
        o = []
        for fr, g in zip(frames, ifgs):
            o.append(f'TXF t=0 ifg={g} nib={16 + 2 * len(fr)} data=' + pre
                     + ''.join('%x%x' % (b & 15, b >> 4) for b in fr))
        line = dict(rep, n=1, rc=round(25e6 * 2 ** SCALED['WIN_LOG2'] * TB_MCLK_NS * 1e-9), ed=0, **cnts)
        o.append('UART|' + fmt_line(line))
        o.append(f'TB model_errors={errors} mdio_frames=66 mdio_x=0 tx_frames={len(frames)} uart_framing=0 lines=1')
        return '\n'.join(o) + '\n'
    ok_ifg = [500] + [IFG_NIB] * (len(want) - 1)
    check('judge passes a correct run', judge(sc, fake(want, ok_ifg, cnt))[0] == [])
    w1 = [bytearray(x) for x in want]
    w1[1][50] ^= 0x04
    check('judge fails one payload bit (FCS fixed up)',
          judge(sc, fake([bytes(w1[0]), bytes(w1[1][:-4]) + fcs(bytes(w1[1][:-4]))], ok_ifg, cnt))[0] != [])
    check('judge fails a wrong FCS', judge(sc, fake([want[0], bytes(w1[1])], ok_ifg, cnt))[0] != [])
    check('judge fails a missing reply', judge(sc, fake(want[:1], ok_ifg, cnt))[0] != [])
    check('judge fails a queued reply after 26 idle nibbles', judge(sc, fake(want, [500, 26], cnt))[0] != [])
    check('judge fails a short IFG', judge(sc, fake(want, [500, 22], cnt))[0] != [])
    check('judge fails a 14-nibble preamble', judge(sc, fake(want, ok_ifg, cnt, pre='5' * 14 + 'd'))[0] != [])
    check('judge fails a counter off by one', judge(sc, fake(want, ok_ifg, dict(cnt, er=cnt['er'] + 1)))[0] != [])
    check('judge fails a model error', judge(sc, fake(want, ok_ifg, cnt, errors=1))[0] != [])
    unpadded = want[0][:-4]
    check('judge fails a frame not padded to 60',
          judge([s for s in scenarios() if s['name'] == 'icmp_56'][0],
                fake([unpadded[:44] + fcs(unpadded[:44])], [500], expect(
                    [s for s in scenarios() if s['name'] == 'icmp_56'][0])[1]))[0] != [])
    words = stim_words([F(b'\x12', gap=5000, odd=0xA)])
    check('stimulus words: bytes, lone nibble, long gap split', words == ['1020'] + ['0055'] * 7 + ['00D5', '0012', '300A', '1FFF', '1389', 'F000'])
    judge_self_test(check)
    return bad


# ------------------------------------------------------------------ board
def read_port(port, baud, count):
    import serial  # pyserial; only this path needs it
    mid = sum(CFGMCLK_HZ) / 2
    print(f'reading {count} report lines from {port} at {baud} (E3 bitstream must be on the board)')
    with serial.Serial(port, baud, timeout=2) as ser:
        got, t0, rows = 0, time.time(), []
        while got < count and time.time() - t0 < count * 1.5 + 5:
            raw = ser.readline().decode('ascii', 'replace')
            r = parse(raw)
            if r:
                got += 1
                print(f'  {raw.strip()}\n    {describe(r, mid)}')
                rows.append(r)
    if rows:
        d = {k: (rows[-1][k] - rows[0][k]) & 0xFFFF for k in COUNTERS + ('ed',)}
        print('board: first to last line: ' + ' '.join(f'{k}+{v}' for k, v in d.items())
              + f"; lk={rows[-1]['lk']}; in-band {rows[-1]['ibl']:X}")
    print(f'board: {got}/{count} lines read. RESULT below counts lines read; the ping verdict is the '
          'host\'s ping output and these counters.')
    return 0 if got == count else 1


# ------------------------------------------------------------------ judge (board logs)
# The verdict on the board step, fixed before it runs: specs/trinet/eth_arp_icmp_e3_ax7203.t27 holds
# the numbers and the rules, conformance/eth_arp_icmp_e3_params.py is generated from it, and the spec
# pins this file's bytes, so the judge cannot change after the logs exist.
E3_LOGS = ('LOG_PREPING', 'LOG_FLASH', 'LOG_BEFORE', 'LOG_PING', 'LOG_ARP', 'LOG_AFTER')
PING_SUM = re.compile(r'^(\d+) packets transmitted, (\d+) (?:packets )?received', re.M)


def load_params():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import eth_arp_icmp_e3_params as p
    return p


def check_pins(p):
    """The spec, the design files, the bitstream record and this checker must be the bytes the spec names."""
    import hashlib
    S = p.SPEC
    pairs = [(p.SPEC_FILE, p.SPEC_SHA256), (S['RUNNER'], S['RUNNER_SHA256'])]
    pairs += [(S[k], S[k[:-5] + '_SHA256']) for k in sorted(S) if k.endswith('_FILE')]
    bad = []
    for rel, want in pairs:
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            bad.append(f'{rel} missing')
            continue
        with open(path, 'rb') as fh:
            if hashlib.sha256(fh.read()).hexdigest() != want:
                bad.append(f'{rel}: sha256 differs from the spec')
    return bad


def _head(text, key):
    m = re.search(r'^# %s (.*)$' % key, text, re.M)
    return m.group(1).strip() if m else None


def _arp_mac(text, ip):
    """MAC in `arp -an` for ip -> bytes, or None (absent or incomplete)."""
    m = re.search(r'\(%s\) at ([0-9a-fA-F]{1,2}(?::[0-9a-fA-F]{1,2}){5})\b' % re.escape(ip), text)
    return bytes(int(x, 16) for x in m.group(1).split(':')) if m else None


def judge_board(logs, S):
    """logs: spec log key -> text of that tri fpga-run log. Returns (verdict, facts, problems); with
    problems the logs cannot be judged and verdict is None."""
    prob, facts = [], {}
    ip = S['IP_TEXT']
    uart_cmd = 'eth_arp_icmp_ax7203.py --port '
    want = {'LOG_PREPING': f"ping -c {S['PRE_PING_COUNT']} {ip}", 'LOG_BEFORE': uart_cmd,
            'LOG_PING': f"ping -c {S['PING_COUNT']} {ip}", 'LOG_ARP': 'arp -an', 'LOG_AFTER': uart_cmd}
    starts = []
    for k in E3_LOGS:
        t = logs.get(k)
        if t is None:
            prob.append(f'{S[k]}: log missing')
            continue
        start, end = _head(t, 'start'), _head(t, 'end')
        if not start or not end or not re.search(r'^# exit=-?\d+$', t, re.M):
            prob.append(f'{S[k]}: no # start, # exit= or # end line')
        starts.append(start or '')
        cmd = _head(t, 'cmd') or ''
        if k in want and want[k] not in cmd:
            prob.append(f'{S[k]}: # cmd does not contain {want[k]!r}')
        if k in ('LOG_BEFORE', 'LOG_AFTER') and not cmd.endswith(f"--lines {S['UART_LINES']}"):
            prob.append(f"{S[k]}: # cmd does not end with --lines {S['UART_LINES']}")
    if prob:
        return None, facts, prob
    if starts != sorted(starts):
        prob.append('logs are not in the order ' + ' < '.join(S[k] for k in E3_LOGS) + ' by # start')
    fl = logs['LOG_FLASH']
    if not (_head(fl, 'bit') or '').endswith(' payload ' + S['PAYLOAD_SHA256']):
        prob.append(f"{S['LOG_FLASH']}: # bit line does not name payload {S['PAYLOAD_SHA256'][:16]}")
    if not re.search(r'^# exit=0$', fl, re.M) or 'loaded file' not in fl:
        prob.append(f"{S['LOG_FLASH']}: the load did not finish (exit=0 and 'loaded file')")
    sums = {k: PING_SUM.search(logs[k]) for k in ('LOG_PREPING', 'LOG_PING')}
    for k, m in sums.items():
        if not m:
            prob.append(f'{S[k]}: no "N packets transmitted, M packets received" line')
    rows = {k: [r for r in map(parse, logs[k].splitlines()) if r] for k in ('LOG_BEFORE', 'LOG_AFTER')}
    for k, rs in rows.items():
        if not rs:
            prob.append(f'{S[k]}: no E3 report line')
    if prob:
        return None, facts, prob
    facts['pre_tx'], facts['pre_rx'] = map(int, sums['LOG_PREPING'].groups())
    facts['tx'], facts['rx'] = map(int, sums['LOG_PING'].groups())
    mac = _arp_mac(logs['LOG_ARP'], ip)
    facts['arp_mac'] = mac.hex(':') if mac else None
    want_mac = (S['MAC_HI16'] << 32 | S['MAC_LO32']).to_bytes(6, 'big')
    b, a = rows['LOG_BEFORE'], rows['LOG_AFTER']
    lines = b + a
    facts['lines'] = (len(b), len(a))
    facts['all_link'] = all(r['lk'] == 1 and (r['ibh'] << 4 | r['ibl']) == S['IB'] for r in lines)
    facts['all_id'] = all(r['id'] == S['PHY_ID'] for r in lines)
    facts['rc'] = (min(r['rc'] for r in lines), max(r['rc'] for r in lines))
    rc_ok = S['RC_MIN'] <= facts['rc'][0] and facts['rc'][1] <= S['RC_MAX']
    d = {k: (a[-1][k] - b[-1][k]) & 0xFFFF for k in ('n',) + COUNTERS + ('ed',)}
    facts['d'] = d
    if facts['pre_rx'] > S['PRE_PING_MAX_REPLIES']:
        return 'CONFLICT', facts, prob
    h1 = dict(ping_sent=facts['tx'] == S['PING_COUNT'], ping_replies=facts['rx'] >= S['PING_MIN_REPLIES'],
              arp_mac=mac == want_mac, eq_covers_replies=d['eq'] >= facts['rx'], er_eq=d['er'] == d['eq'],
              arp_seen=d['aq'] >= 1, ar_aq=d['ar'] == d['aq'], link=facts['all_link'], phy_id=facts['all_id'],
              rc=rc_ok)
    facts['h1_failed'] = [k for k, ok in h1.items() if not ok]
    if not facts['h1_failed']:
        return 'H1', facts, prob
    if not facts['all_link']:
        return 'H4', facts, prob
    if d['aq'] == 0 and d['eq'] == 0:
        return 'H3', facts, prob
    if (d['ar'] >= 1 or d['er'] >= 1) and facts['rx'] == 0:
        return 'H2', facts, prob
    return 'OTHER', facts, prob


def judge_main(runs):
    p = load_params()
    S = p.SPEC
    print(f"judge: spec {p.SPEC_FILE} sha256 {p.SPEC_SHA256[:16]}, checker {S['RUNNER_SHA256'][:16]}, "
          f"payload {S['PAYLOAD_SHA256'][:16]}")
    bad = check_pins(p)
    logs = {}
    for k in E3_LOGS:
        path = os.path.join(runs, S[k] + '.log')
        if os.path.exists(path):
            with open(path, encoding='utf-8', errors='replace') as fh:
                logs[k] = fh.read()
            print(f"  {S[k]}.log  # start {_head(logs[k], 'start')}")
    verdict, facts, prob = (None, {}, []) if bad else judge_board(logs, S)
    for x in bad + prob:
        print(f'  REFUSED {x}')
    if verdict is None:
        print('E3 VERDICT none: the logs cannot be judged (above); nothing about the design follows')
        print('RESULT FAIL (not judged)')
        return 2
    for k, v in facts.items():
        print(f'  {k} = {v}')
    print(f'E3 VERDICT {verdict}')
    print('RESULT', 'PASS' if verdict == 'H1' else f'FAIL ({verdict})')
    return 0 if verdict == 'H1' else 1


def judge_self_test(check):
    """Made-up logs against the generated params: the right run, then wrong in one detail each."""
    try:
        S = load_params().SPEC
    except ImportError as e:
        check(f'judge: params import ({e})', False)
        return
    ip = S['IP_TEXT']
    mac_arp = ':'.join('%x' % x for x in (S['MAC_HI16'] << 32 | S['MAC_LO32']).to_bytes(6, 'big'))
    rc_mid = (S['RC_MIN'] + S['RC_MAX']) // 2

    def wrap(t, cmd, body, code=0, bit=''):
        return (f'# start 2026-09-28T00:{t:02d}:00Z\n{bit}# usb HUB [\'0x110000\']\n# cmd {cmd}\n# limit 600 s\n'
                f'{body}\n# exit={code}\n# end 2026-09-28T00:{t:02d}:30Z\n')

    def uart(t, start, n0, **over):
        rows = []
        for i in range(S['UART_LINES']):
            r = dict(n=n0 + i, pm=3, id=S['PHY_ID'], sr2=0x796D, pc=0x28, ibh=S['IB'] >> 4, ibl=S['IB'] & 15,
                     rc=rc_mid, lk=1)
            r.update(start)
            r.update(over)
            rows.append('  ' + fmt_line(r) + '\n    ' + describe(parse(fmt_line(r))))
        return wrap(t, f"python3 -u eth_arp_icmp_ax7203.py --port /dev/cu.usbserial-110 --lines {S['UART_LINES']}",
                    '\n'.join(rows))

    def ping(t, count, got):
        return wrap(t, f'ping -c {count} {ip}', f'--- {ip} ping statistics ---\n{count} packets transmitted, '
                    f'{got} packets received, {100 * (count - got) / count:.1f}% packet loss', 0 if got else 2)

    def logs(pre=0, got=None, arp=mac_arp, before=None, after=None, after_over=None, payload=None, order=None):
        got = S['PING_COUNT'] if got is None else got
        before = before or dict(rx=0x30, aq=0, ar=0, eq=0, er=0)
        after = after or dict(rx=(before['rx'] + 25) & 0xFFFF, aq=(before['aq'] + 1) & 0xFFFF,
                              ar=(before['ar'] + 1) & 0xFFFF, eq=(before['eq'] + got) & 0xFFFF,
                              er=(before['er'] + got) & 0xFFFF)
        t = order or (0, 1, 3, 4, 5, 6)
        arp_line = f'? ({ip}) at {arp} on en0 ifscope [ethernet]' if arp else f'? ({ip}) at (incomplete) on en0'
        return dict(
            LOG_PREPING=ping(t[0], S['PRE_PING_COUNT'], pre),
            LOG_FLASH=wrap(t[1], 'sudo /opt/homebrew/bin/openocd ...', 'loaded file e3.bit to pld device 0',
                           bit=f"# bit /x/e3.bit payload {payload or S['PAYLOAD_SHA256']}\n"),
            LOG_BEFORE=uart(t[2], before, 0x100),
            LOG_PING=ping(t[3], S['PING_COUNT'], got),
            LOG_ARP=wrap(t[4], 'arp -an', '? (192.168.1.1) at 0:11:22:33:44:55 on en0 ifscope [ethernet]\n' + arp_line),
            LOG_AFTER=uart(t[5], after, 0x160, **(after_over or {})))

    def v(**kw):
        return judge_board(logs(**kw), S)[0]

    check('judge: a right run is H1', v() == 'H1')
    check(f"judge: {S['PING_MIN_REPLIES']} replies of {S['PING_COUNT']} is H1", v(got=S['PING_MIN_REPLIES']) == 'H1')
    check(f"judge: {S['PING_MIN_REPLIES'] - 1} replies is not H1", v(got=S['PING_MIN_REPLIES'] - 1) == 'OTHER')
    check('judge: counters that wrap between the reads still give H1',
          v(before=dict(rx=0xFFF0, aq=0xFFFF, ar=0xFFFF, eq=0xFFFE, er=0xFFFE)) == 'H1')
    check('judge: one echo reply short of the requests is not H1',
          v(after=dict(rx=0x50, aq=1, ar=1, eq=S['PING_COUNT'], er=S['PING_COUNT'] - 1)) == 'OTHER')
    check('judge: no ARP request counted is not H1',
          v(after=dict(rx=0x50, aq=0, ar=0, eq=S['PING_COUNT'], er=S['PING_COUNT'])) == 'OTHER')
    check('judge: another MAC in the ARP table is not H1', v(arp='0:11:22:33:44:66') == 'OTHER')
    check('judge: rc one above the bound is not H1', v(after_over=dict(rc=S['RC_MAX'] + 1)) == 'OTHER')
    check('judge: rc one below the bound is not H1', v(after_over=dict(rc=S['RC_MIN'] - 1)) == 'OTHER')
    check('judge: rc on both bounds is H1', v(before=dict(rx=0x30, aq=0, ar=0, eq=0, er=0, rc=S['RC_MIN']),
                                            after_over=dict(rc=S['RC_MAX'])) == 'H1')
    check('judge: another PHY id is not H1', v(after_over=dict(id=S['PHY_ID'] + 1)) == 'OTHER')
    check('judge: lk=0 on the after lines is H4', v(after_over=dict(lk=0)) == 'H4')
    check('judge: in-band 0x3 (10M) is H4', v(after_over=dict(ibl=3)) == 'H4')
    check('judge: frames seen, none of ours recognised is H3',
          v(got=0, arp=None, after=dict(rx=0x90, aq=0, ar=0, eq=0, er=0)) == 'H3')
    check('judge: replies counted on the board, none on the host is H2',
          v(got=0, arp=None, after=dict(rx=0x90, aq=3, ar=3, eq=0, er=0)) == 'H2')
    check('judge: an answer at the address before the flash is CONFLICT', v(pre=1) == 'CONFLICT')
    check('judge: another payload in the flash log is refused', v(payload='0' * 64) is None)
    check('judge: logs out of order are refused', v(order=(0, 1, 4, 3, 5, 6)) is None)
    lg = logs()
    lg['LOG_PING'] = lg['LOG_PING'].replace(f"ping -c {S['PING_COUNT']} ", 'ping -c 5 ')
    check('judge: a ping with another count is refused', judge_board(lg, S)[0] is None)
    lg = logs()
    lg['LOG_AFTER'] = lg['LOG_AFTER'].replace(f"--lines {S['UART_LINES']}", '--lines 3')
    check('judge: a UART read of another length is refused', judge_board(lg, S)[0] is None)
    del lg['LOG_ARP']
    check('judge: a missing log is refused', judge_board(lg, S)[0] is None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--static', action='store_true')
    ap.add_argument('--sim', action='store_true')
    ap.add_argument('--gate', action='store_true')
    ap.add_argument('--only', nargs='+', metavar='SCENARIO', help='run only these scenarios')
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--parse', metavar='FILE')
    ap.add_argument('--port')
    ap.add_argument('--baud', type=int, default=1144744)
    ap.add_argument('--lines', type=int, default=20)
    ap.add_argument('--judge', action='store_true', help='verdict on the board step from its six logs')
    ap.add_argument('--runs', default=os.path.join(REPO, 'conformance', 'board_runs'))
    a = ap.parse_args()
    if a.judge:
        return judge_main(a.runs)
    if not (a.self_test or a.static or a.sim or a.gate or a.parse or a.port):
        a.self_test = a.static = a.sim = a.gate = True
    fails = 0
    if a.self_test:
        fails += self_test()
    if a.static:
        fails += static()
    if a.sim:
        fails += sim(False, a.only, a.jobs)
    if a.gate:
        fails += sim(True, a.only, a.jobs)
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
