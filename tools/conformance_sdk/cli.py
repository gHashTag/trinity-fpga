"""CLI entry: `python -m tools.conformance_sdk ...`

Examples:
  python -m tools.conformance_sdk report
  python -m tools.conformance_sdk check --format nf4 --decoder mymod:my_decode
  python -m tools.conformance_sdk check --format mxfp8_e4m3 --decoder mymod:decode --random 5000
  python -m tools.conformance_sdk encode --format fp8_e4m3 --value 0.375
  python -m tools.conformance_sdk roundtrip --format fp8_e4m3
  python -m tools.conformance_sdk fp8-audit --format fp8_e4m3
"""
from __future__ import annotations
import argparse
import importlib


def _load_callable(spec: str):
    if ":" in spec:
        mod, fn = spec.split(":", 1)
    elif "." in spec:
        mod, fn = spec.rsplit(".", 1)
    else:
        raise SystemExit("--decoder must be 'module:func' or 'module.func'")
    m = importlib.import_module(mod)
    return getattr(m, fn)


def main():
    ap = argparse.ArgumentParser(prog="conformance-sdk",
                                 description="Audit decoders against Trinity golden oracles")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_rep = sub.add_parser("report", help="catalog status (all formats / families)")
    p_rep.add_argument("-v", "--verbose", action="store_true")

    p_chk = sub.add_parser("check", help="audit one decoder vs golden")
    p_chk.add_argument("--format", required=True, help="format name (e.g. nf4, mxfp8_e4m3, fp8_e4m3)")
    p_chk.add_argument("--decoder", required=True,
                       help="user decoder as 'module:func' or 'module.func' (func(raw)->value)")
    p_chk.add_argument("--random", type=int, default=1000, help="random vectors (0 = vectors only)")
    p_chk.add_argument("--seed", type=int, default=0)
    p_chk.add_argument("--no-vectors", action="store_true", help="skip SSOT vector raws")

    p_enc = sub.add_parser("encode", help="encode one value into a format (shows raw + round-trip)")
    p_enc.add_argument("--format", required=True, help="format name (e.g. fp8_e4m3)")
    p_enc.add_argument("--value", required=True,
                       help="decimal ('0.375'), fraction ('3/8'), or nan/inf/-inf")

    p_rt = sub.add_parser("roundtrip", help="audit encode/decode round-trip vs golden")
    p_rt.add_argument("--format", required=True)
    p_rt.add_argument("--random", type=int, default=4096,
                      help="random raws when width > exhaustive threshold")
    p_rt.add_argument("--seed", type=int, default=0)

    p_fp8 = sub.add_parser("fp8-audit",
                           help="audit a naive IEEE fp8 decoder vs golden (built-in)")
    p_fp8.add_argument("--format", default="fp8_e4m3",
                       help="fp8_e4m3 (default) or fp8_e5m2")

    args = ap.parse_args()

    try:
        return _dispatch(args)
    except KeyError as e:
        # unknown format name from the registry
        print(f"error: {e.args[0] if e.args else e}")
        return 2


def _dispatch(args):
    if args.cmd == "report":
        from .checker import audit_report
        print(audit_report(verbose=args.verbose))
        return 0

    if args.cmd == "check":
        from .checker import check_decoder
        user_decode = _load_callable(args.decoder)
        r = check_decoder(args.format, user_decode, n_random=args.random,
                          seed=args.seed, use_vectors=not args.no_vectors)
        print(f"[{r['format']}] family={r['family']} width={r['width']}")
        print(f"  matched {r['matched']}/{r['total']}  rate={r['rate']:.4%}")
        if r["mismatches"]:
            print("  first mismatches:")
            for m in r["mismatches"]:
                print(f"    raw=0x{m['raw']:x}  golden={m['golden']}  user={m['user']}")
        return 0 if r["rate"] == 1.0 else 1

    if args.cmd == "encode":
        from .roundtrip import encode_value
        r = encode_value(args.format, args.value)
        print(f"[{r['format']}] w={r['width']}  input={r['input']}")
        print(f"  raw = {r['raw_hex']}  ({r['raw_bin']})")
        print(f"  decodes back to: {r['decodes_to']}")
        if r["exact"] is not None:
            print(f"  exact (no rounding): {r['exact']}")
        return 0

    if args.cmd == "roundtrip":
        from .roundtrip import check_roundtrip
        r = check_roundtrip(args.format, n_random=args.random, seed=args.seed)
        if r.get("skipped"):
            print(f"[{r['format']}] SKIP  ({r['reason']})")
            return 0
        print(f"[{r['format']}] family={r['family']} width={r['width']}  mode={r['mode']}")
        print(f"  encode-stable (raw->val->raw): {r['stable_ok']}/{r['stable_total']}"
              f"  rate={r['stable_rate']:.4%}")
        print(f"  idempotent    (val->raw->raw): {r['idem_ok']}/{r['idem_total']}"
              f"  rate={r['idem_rate']:.4%}")
        if r["fails"]:
            print("  first failures:")
            for f in r["fails"]:
                print("    " + "  ".join(f"{k}={v}" for k, v in f.items()))
        return 0 if (r["stable_rate"] == 1.0 and r["idem_rate"] == 1.0) else 1

    if args.cmd == "fp8-audit":
        from .fp8_audit import audit_fp8
        r = audit_fp8(args.format)
        print(f"[{r['format']}] naive-IEEE decoder vs golden  (full {r['total']}-code sweep)")
        print(f"  matched {r['matched']}/{r['total']}  rate={r['rate']:.4%}"
              f"  divergences={r['diverge_count']}")
        print(f"  note: {r['note']}")
        if r["diverge"]:
            print("  naive decoder is WRONG at:")
            for d in r["diverge"]:
                print(f"    raw=0x{d['raw']:02x}  golden={d['golden']:<10}  naive={d['naive']}")
        return 0 if r["rate"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
