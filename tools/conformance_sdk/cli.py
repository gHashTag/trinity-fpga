"""CLI entry: `python -m tools.conformance_sdk ...`

Examples:
  python -m tools.conformance_sdk report
  python -m tools.conformance_sdk check --format nf4 --decoder mymod:my_decode
  python -m tools.conformance_sdk check --format mxfp8_e4m3 --decoder mymod:decode --random 5000
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

    args = ap.parse_args()

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


if __name__ == "__main__":
    raise SystemExit(main())
