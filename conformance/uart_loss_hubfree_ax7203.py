#!/usr/bin/env python3
"""UART loss at window 24 with no hub between the CP2102N and the Mac: one long arm, counted.

Pre-registered in specs/trinet/uart_loss_hubfree_ax7203.t27; every number comes from the generated
uart_loss_hubfree_params.py. The counter is the diagnostic's, uart_loss_diag_ax7203.run_arm and
.summarize, imported and pinned by sha256, never edited; it reads its frame constants from its own
params, which the spec also pins, and this runner checks that the constants the spec repeats are the
ones the counter uses. What this file adds:

  * a USB check before the first byte: exactly one CP2102N in the IOUSB plane, and no hub (device
    class 9) between it and its host controller; otherwise nothing is sent;
  * the pre-registered claim: zero loss events in JOBS_PER_ARM answers puts the one-sided 95 % bound
    on the loss-event rate, ln(20) / JOBS_PER_ARM, below one per generation run.

    python3 uart_loss_hubfree_ax7203.py --usb
    python3 uart_loss_hubfree_ax7203.py --self-test
    python3 uart_loss_hubfree_ax7203.py --run --setkey --port /dev/cu.usbserial-NNN \\
        --keys ../trinet-keys.txt --json board_runs/uart_loss_hubfree_w24.json

Author: Dmitrii Vasilev (@gHashTag)
"""
import argparse
import hashlib
import json
import math
import os
import plistlib
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from uart_loss_hubfree_params import SPEC as S, SPEC_FILE, SPEC_SHA256  # noqa: E402
import uart_loss_diag_ax7203 as d  # noqa: E402
import tern_tc_layer_ax7203 as h  # noqa: E402

REPEATED = ("NODE_ID", "BAUD", "RESP_LEN", "FIRST_JOB_NONCE", "JOBS_PER_PASS", "READ_TIMEOUT_S")


def sha256_file(rel):
    with open(os.path.join(REPO, rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def pins_ok(log=print):
    """This spec, the diagnostic's spec, params and runner, the harness, MAC32 and the generation
    params must be the bytes the spec names; the counter must use the constants the spec repeats."""
    ok = True
    for rel, want in ((SPEC_FILE, SPEC_SHA256), (S["DIAG_SPEC_FILE"], S["DIAG_SPEC_SHA256"]),
                      (S["DIAG_PARAMS_FILE"], S["DIAG_PARAMS_SHA256"]),
                      (S["DIAG_RUNNER_FILE"], S["DIAG_RUNNER_SHA256"]),
                      (S["HARNESS_FILE"], S["HARNESS_SHA256"]), (S["MAC32_FILE"], S["MAC32_SHA256"]),
                      (S["GENERATE_PARAMS_FILE"], S["GENERATE_PARAMS_SHA256"])):
        got = sha256_file(rel)
        if got != want:
            log(f"PIN MISMATCH {rel}: {got[:16]} != {want[:16]}; nothing run")
            ok = False
    for k in REPEATED:
        if d.SPEC[k] != S[k]:
            log(f"MISMATCH {k}: counter uses {d.SPEC[k]}, spec says {S[k]}; nothing run")
            ok = False
    if d.SPEC["ARM_WINDOWS"][S["DIAG_ARM"]] != S["WINDOW"] or d.RESP_LEN != S["RESP_LEN"] \
            or d.FIRST != S["FIRST_JOB_NONCE"]:
        log("MISMATCH: the counter's window, RESP_LEN or first nonce differ from the spec; nothing run")
        ok = False
    return ok


# ---------------------------------------------------------------------------
# USB path
# ---------------------------------------------------------------------------

def usb_tree():
    raw = subprocess.run(["ioreg", "-p", "IOUSB", "-w0", "-a", "-l"], capture_output=True,
                         check=True).stdout
    return plistlib.loads(raw)


def usb_paths(tree, vendor, product):
    """Every device vendor:product, each as its list of ancestors from the root down to itself."""
    found = []

    def walk(n, path):
        me = path + [n]
        if n.get("idVendor") == vendor and n.get("idProduct") == product:
            found.append(me)
        for c in n.get("IORegistryEntryChildren", []):
            walk(c, me)
    walk(tree, [])
    return found


def describe(n):
    name = n.get("USB Product Name") or n.get("IORegistryEntryName") or "?"
    if n.get("idVendor") is None:
        return name
    return f"{name} {n['idVendor']:04x}:{n['idProduct']:04x} @ {n.get('locationID', 0):#010x}"


def usb_check(tree, log=print):
    """(ok, text): ok iff exactly one CP2102N and at most HUBS_ALLOWED hubs above it."""
    paths = usb_paths(tree, S["USB_VENDOR"], S["USB_PRODUCT"])
    if len(paths) != 1:
        return False, f"{len(paths)} CP2102N devices in the IOUSB plane, want exactly 1"
    path = paths[0]
    hubs = [n for n in path[:-1] if n.get("bDeviceClass") == S["HUB_CLASS"]]
    text = " -> ".join(describe(n) for n in path[1:])
    if len(hubs) > S["HUBS_ALLOWED"]:
        return False, f"{text}; {len(hubs)} hub(s) in the path: " + ", ".join(describe(n) for n in hubs)
    return True, f"{text}; no hub in the path"


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------

def claim(res, summary, log=print):
    """The pre-registered rule; returns 'yes', 'no' or 'not decidable'."""
    n, k = res["sent"], summary["loss_events"]
    broken = (not summary["instrument_ok"] or res["aborted"] or res["stopped_at_limit"]
              or n != S["JOBS_PER_ARM"] or res["wrong_y"])
    bound = math.log(20) / n if n else float("inf")
    per_gen = bound * S["JOBS_GEN"]
    if res["wrong_y"]:
        log(f"COMPUTE FAULT: {res['wrong_y']} answers carry a valid tag and a wrong y; not a UART loss")
    if broken:
        verdict = "not decidable"
        log("CLAIM_BELOW_ONE_PER_GENERATION_RUN: not decidable (arm aborted, cut short, a wrong y, "
            "or the instrument check failed)")
    elif k == 0:
        verdict = "yes" if per_gen < 1 else "no"
        log(f"one-sided 95 % bound: {1e6 * bound:.4f} loss events per 10^6 answers, "
            f"{per_gen:.3f} per generation run of {S['JOBS_GEN']} answers")
        log(f"CLAIM_BELOW_ONE_PER_GENERATION_RUN: {verdict}")
    else:
        verdict = "no"
        log(f"point estimate: {k * S['JOBS_GEN'] / n:.2f} loss events per generation run of "
            f"{S['JOBS_GEN']} answers ({k} in {n})")
        log(f"CLAIM_BELOW_ONE_PER_GENERATION_RUN: no ({k} loss event(s))")
    return verdict


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _dev(name, vid, pid, cls, loc, kids=()):
    return {"IORegistryEntryName": name, "USB Product Name": name, "idVendor": vid, "idProduct": pid,
            "bDeviceClass": cls, "locationID": loc, "IORegistryEntryChildren": list(kids)}


def self_test():
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(f"  [{'ok ' if cond else 'FAIL'}] {msg}")
        ok &= bool(cond)

    quiet = lambda *_: None  # noqa: E731
    print("self-test uart_loss_hubfree_ax7203:")
    check(pins_ok(log=lambda s: print("  " + s)), "pins, and the counter's constants equal the spec's")
    vid, pid = S["USB_VENDOR"], S["USB_PRODUCT"]
    cp = lambda loc: _dev("CP2102N USB to UART Bridge Controller", vid, pid, 0, loc)  # noqa: E731
    xhci = lambda *kids: {"IORegistryEntryName": "AppleT6000USBXHCI",  # noqa: E731
                          "IORegistryEntryChildren": list(kids)}
    root = lambda *ctl: {"IORegistryEntryName": "Root", "IORegistryEntryChildren": list(ctl)}  # noqa: E731
    genesys = root(xhci(_dev("USB2.1 Hub", 0x05e3, 0x0610, 9, 0x00100000, [cp(0x00110000)])))
    direct = root(xhci(cp(0x00100000)), xhci(_dev("USB2.0 HUB", 0x1a40, 0x0101, 9, 0x01100000,
                                                  [_dev("Digilent USB Device", 0x0403, 0x6014, 0, 0x01140000)])))
    two = root(xhci(cp(0x00100000)), xhci(cp(0x01100000)))
    none = root(xhci())
    check(not usb_check(genesys)[0] and "05e3:0610" in usb_check(genesys)[1],
          "USB check refuses the CP2102N behind the Genesys hub")
    check(usb_check(direct)[0], "USB check accepts the CP2102N on a controller port, hub elsewhere")
    check(not usb_check(two)[0] and not usb_check(none)[0], "USB check refuses two CP2102N and none")
    try:
        live_ok, live = usb_check(usb_tree())
        print(f"  [info] this Mac now: {live} -> {'would run' if live_ok else 'would refuse'}")
    except (OSError, subprocess.CalledProcessError, plistlib.InvalidFileException) as e:
        print(f"  [info] ioreg not readable here ({e}); the board run refuses without it")

    # The counter, pinned, on the reference cell: a clean stretch and one 56-byte hole.
    rnd = __import__("random").Random(24)
    jobs = [(bytes(rnd.randrange(256) for _ in range(8)), bytes(rnd.randrange(256) for _ in range(8)),
             0, 1) for _ in range(101)]
    cell = lambda: h.RefCell(node_id=S["NODE_ID"], key=h.TEST_KEY)  # noqa: E731
    r0 = d.run_arm(cell(), jobs, 3000, h.TEST_KEY, S["WINDOW"], log=quiet)
    s0 = d.summarize(r0, log=quiet)
    check(s0["loss_events"] == 0 and r0["accepted"] == 3000 and s0["instrument_ok"],
          f"pinned counter, window {S['WINDOW']}, clean: 3000/3000 accepted, 0 loss events")
    r1 = d.run_arm(d.HoleLink(cell(), [(19 * 1200 + 1, 56)]), jobs, 3000, h.TEST_KEY, S["WINDOW"], log=quiet)
    s1 = d.summarize(r1, log=quiet)
    check(s1["loss_events"] == 1 and s1["holes"] == [56] and s1["instrument_ok"],
          "pinned counter: the generation run's 56-byte hole is one loss event of 56 bytes")

    # The claim rule, on records shaped like the counter's.
    def rec(sent, k=0, wrong_y=0, aborted=None, stopped=False, inst=True):
        return (dict(sent=sent, wrong_y=wrong_y, aborted=aborted, stopped_at_limit=stopped),
                dict(loss_events=k, instrument_ok=inst))
    N = S["JOBS_PER_ARM"]
    check(claim(*rec(N), log=quiet) == "yes", f"claim: 0 events in {N} -> yes")
    check(claim(*rec(N, k=1), log=quiet) == "no", "claim: 1 event -> no")
    check(claim(*rec(N - S["JOBS_PER_PASS"]), log=quiet) == "not decidable", "claim: one pass short -> not decidable")
    check(claim(*rec(N, stopped=True), log=quiet) == "not decidable", "claim: stopped at the limit -> not decidable")
    check(claim(*rec(N, wrong_y=1), log=quiet) == "not decidable", "claim: a wrong y -> not decidable")
    check(claim(*rec(N, inst=False), log=quiet) == "not decidable", "claim: instrument broken -> not decidable")
    b = math.log(20) / N * S["JOBS_GEN"]
    b_short = math.log(20) / (N - S["JOBS_PER_PASS"]) * S["JOBS_GEN"]
    check(b < 1 <= b_short, f"bound: {b:.4f} per generation run at {S['PASSES']} passes, "
          f"{b_short:.4f} at {S['PASSES'] - 1}")
    p0 = math.exp(-N * S["PRIOR_HUB_W24_EVENTS"] / S["PRIOR_HUB_W24_ANSWERS"])
    check(0.05 < p0 < 0.10, f"at the hub path's point rate, P[0 events in this arm] = {p0:.3f}")
    print(f"self-test uart_loss_hubfree_ax7203: {'PASS' if ok else 'FAIL'}")
    return ok


# ---------------------------------------------------------------------------

def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--usb", action="store_true", help="print the CP2102N's USB path and the check")
    a.add_argument("--self-test", action="store_true")
    a.add_argument("--run", action="store_true", help="the board arm")
    a.add_argument("--port")
    a.add_argument("--keys", default="../trinet-keys.txt")
    a.add_argument("--node", default="node0")
    a.add_argument("--setkey", action="store_true")
    a.add_argument("--json", help="write the arm's record here")
    args = a.parse_args()
    if args.self_test:
        return 0 if self_test() else 1
    if args.usb:
        good, text = usb_check(usb_tree())
        print(("USB ok: " if good else "USB refused: ") + text)
        return 0 if good else 1
    if not args.run:
        a.error("give --usb, --self-test or --run")
    if not args.port:
        a.error("--run needs --port (the hub-free port name is not guessed)")
    if not pins_ok():
        return 2
    good, text = usb_check(usb_tree())
    print(("USB ok: " if good else "USB refused: ") + text)
    if not good:
        print("nothing sent")
        return 2
    if not os.path.exists(args.port):
        print(f"{args.port} does not exist; nothing sent")
        return 2
    window = S["WINDOW"]
    print(f"spec {SPEC_FILE} sha256 {SPEC_SHA256[:16]}; counter {S['DIAG_RUNNER_SHA256'][:16]}, "
          f"harness {S['HARNESS_SHA256'][:16]} (pins checked)")
    mats, _hdr = h.load_tc02(os.path.expanduser(d.SPEC["MODEL"]), h.KINDS, None)
    jobs, _rows = h.build_jobs(mats, "ternary", d.SPEC["N_X"], d.SPEC["SEED"])
    if len(jobs) != S["JOBS_PER_PASS"]:
        print(f"job list has {len(jobs)} entries, spec says {S['JOBS_PER_PASS']}; nothing run")
        return 2
    key = h.load_key(args.keys, args.node)
    print(f"arm: window {window}, {S['JOBS_PER_ARM']} jobs ({S['PASSES']} x {S['JOBS_PER_PASS']}), "
          f"limit {S['LIMIT_S']} s, port {args.port} @ {S['BAUD']}")
    link = h.SerialLink(args.port, S["BAUD"])
    if args.setkey and h.install_key(link, key) is None:
        print("setkey failed before the first job (a retry is allowed once, both logs kept)")
        return 3
    res = d.run_arm(link, jobs, S["JOBS_PER_ARM"], key, window, limit_s=S["LIMIT_S"])
    res["summary"] = d.summarize(res)
    res["claim"] = claim(res, res["summary"])
    res["usb_path"] = text
    res["spec_sha256"] = SPEC_SHA256
    if args.json:
        with open(args.json, "w") as f:
            json.dump(res, f, indent=1)
        print(f"record: {args.json}")
    return 0 if res["summary"]["instrument_ok"] and not res["aborted"] else 1


if __name__ == "__main__":
    sys.exit(main())
